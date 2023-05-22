import json
import random
import string
import time

from confluent_kafka import Consumer, Producer
from fastecdsa import ecdsa, curve
from fastecdsa.point import Point
from sqlalchemy.exc import SQLAlchemyError

from src import db
from src.blockchain import Blockchain
from src.models import Block, Node, Transaction
from src.peer_to_peer import PeerToPeer


class KafkaPeerToPeer(PeerToPeer):

    def __init__(self, app):
        super().__init__(app)
        self.publisher = self.set_publisher()
        self.node_publisher = self.transaction_publisher = self.chain_publisher = self.publisher
        group = ''.join(random.choice(string.ascii_letters + string.digits) for i in range(4))
        self.node_subscriber = self.set_subscriber(group=group, topic='node')
        self.transaction_subscriber = self.set_subscriber(group=group, topic='transaction')
        self.chain_subscriber = self.set_subscriber(group=group, topic='chain')

    def bootstrap(self, *args, **kwargs):
        blockchain = Blockchain(self.app)
        first_node = Node(address=self.app.config['FIRST_NODE'])
        this_node = Node(address=self.app.config['THIS_NODE'])
        if first_node.address != this_node.address:
            # get the genesis block
            if not Block.query.all():
                response = blockchain.get_blocks_from(first_node, 1)
                if response:
                    try:
                        genesis_block = Block()
                        [setattr(genesis_block, key, response[key]) for key in response]
                        db.session.add(genesis_block)
                        db.session.commit()
                        print('Genesis block added.')
                    except SQLAlchemyError as e:
                        print(f'Genesis block could not be added: ', e)
                    except Exception as e:
                        print(f'A problem occurred while adding the genesis block: ', e)
        else:
            if blockchain.create_genesis_block():
                print('Genesis block created.')
            else:
                print('Genesis block already exists.')

    def subscribe_to_node(self, node: Node) -> bool:
        # all of them subscribe to a backbone in kafka
        return True

    def set_publisher(self):
        return Producer({
            'bootstrap.servers': 'localhost:9092'
        })

    def set_subscriber(self, group, topic: str) -> Consumer:
        subscriber = Consumer({
            'bootstrap.servers': 'localhost:9092',
            'auto.offset.reset': 'latest',
            'enable.auto.commit': False,
            'group.id': group,
        })
        subscriber.subscribe([topic], on_assign=self.assignment_callback)
        return subscriber

    def assignment_callback(self, consumer, partitions):
        for p in partitions:
            print(f'Assigned to {p.topic}, partition {p.partition}')

    def broadcast(self, publisher, data, topic):
        print(f'Broadcasting {data} to {topic}')
        publisher.produce(topic, key="key1", value=json.dumps(data), callback=self.acked)
        publisher.poll(1)
        # publisher.flush()

    def acked(self, err, msg):
        if err is not None:
            print("Failed to deliver message: %s: %s" % (str(msg), str(err)))
        else:
            print("Message produced: %s" % (str(msg)))

    def receive_transaction(self):
        event = self.transaction_subscriber.poll(1)
        if event is None:
            # print("No event")
            pass
        elif event.error():
            print(f'Error: {event.error()}')
        else:
            try:
                transaction = json.loads(event.value())
                partition = event.partition()
                print(f'Received: transaction {transaction} from partition {partition}')
                if transaction['id'] != 'None':
                    transaction_id = transaction['id']
                else:
                    transactions = Transaction.query.all()
                    transaction_id = len(transactions) + 1
                received_public_key = transaction['public_key'].split(' ')
                x = int(received_public_key[1].strip()[:-2], 16)
                y = int(received_public_key[2].strip()[:-4], 16)
                public_key = Point(x, y, curve=curve.secp256k1)
                transaction_data_string = transaction['transaction_data_string'][2:-1]
                signature = tuple(json.loads(transaction['signature']))
                valid = ecdsa.verify(signature, str(transaction_data_string), public_key, curve.secp256k1, ecdsa.sha256)
                # if we ratify the transaction sent is valid we store it in the database
                if valid:
                    transaction_db = Transaction()
                    transaction_db.id = transaction_id
                    transaction_db.public_key = public_key
                    transaction_db.transaction_data_string = transaction_data_string
                    transaction_db.signature = json.dumps(signature)
                    transaction_db.valid = valid
                    try:
                        db.session.add(transaction_db)
                        db.session.commit()
                        print(f'Transaction: {transaction_id} added.')
                        transactions = Transaction.query.all()
                        if len(transactions) >= self.app.config['TRANSACTIONS_AMOUNT']:
                            blockchain = Blockchain(self.app)
                            # proof_work generates a new block
                            new_block = blockchain.proof_of_work()
                            db.session.add(new_block)
                            db.session.commit()
                            self.broadcast(self.publisher, blockchain.get_blocks_as_list_of_dict(), topic='chain')
                            db.session.query(Transaction).delete()
                            db.session.commit()
                    except SQLAlchemyError as e:
                        print(f'Transaction {transaction_id} could not be added: ', e)
                        pass
                    except Exception as e:
                        print(f'A problem occurred at receiving transaction: ', e)
                else:
                    print(f'Transaction: {transaction_id} is not valid.')
            except json.decoder.JSONDecodeError as e:
                # Handle the JSONDecodeError exception
                print("Failed to decode JSON:", str(e))
            except Exception as e:
                print(f'A problem occurred at receiving transaction: ', e)

    def receive_node(self):
        event = self.node_subscriber.poll(1.5)
        if event is None:
            # print("No event")
            pass
        else:
            node = json.loads(event.value())
            if type(node) == str:
                node = json.loads(node)
            partition = event.partition()
            print(f'Received: node {node} from partition {partition}')
            # consumer.commit(event)
            received_node = Node(address=node['address'])
            if node['id']:
                received_node.id = node['id']
            try:
                existing_node = Node.query.filter_by(address=received_node.address).all()
                if len(existing_node) >= 1:
                    print(f'Broadcast node: there is at least one node with the same address: {received_node.address}')
                    pass
                else:
                    if received_node.id and received_node.id != 'None':
                        db.session.add(received_node)
                        db.session.commit()
                        print(f'Node: {received_node.id}, {received_node.address} added.')
                    else:
                        print(f'{self.app.config["THIS_NODE"]} did not receive an ID from {received_node.address}')
            except SQLAlchemyError as e:
                # TODO make it more elegant instead of just spit the exception
                print(f'Node {received_node.id}, {received_node.address} could not be added: ', e)
                db.session.rollback()
            except Exception as e:
                print(f'A problem occurred at receiving node: ', e)

    def receive_chain(self):
        event = self.chain_subscriber.poll(1.5)
        if event is None:
            # print("No event")
            pass
        elif event.error():
            print(f'Error: {event.error()}')
        else:
            try:
                received_blocks = event.value()
                partition = event.partition()
                print(f'Received: chain {received_blocks} from partition {partition}')
                stored_blocks = Block.query.all()
                if isinstance(received_blocks, dict) and len(received_blocks) > len(stored_blocks):
                    # first we check the received blocks against what we already have
                    for i in range(len(received_blocks)):
                        if stored_blocks:
                            if stored_blocks[i].as_dict() != received_blocks[i]:
                                print(f'Inconsistency in the chain received compared with the one we already have')
                                # TODO: maybe discard
                                continue
                        try:
                            # what we have is shorter than what we received
                            num_blocks_deleted = db.session.query(Block).delete()
                            print(f'Updating chain: {num_blocks_deleted} blocks deleted.')
                            for block in received_blocks:
                                new_block = Block()
                                [setattr(new_block, key, block[key]) for key in block]
                                db.session.add(new_block)
                            db.session.commit()
                            blockchain = Blockchain(self.app)
                            print(f'Chain updated and broadcast.')
                            self.broadcast(self.publisher, blockchain.get_blocks_as_list_of_dict(), topic='chain')
                            # TODO: delete only required, here we are wiping out everything
                            db.session.query(Transaction).delete()
                            db.session.commit()
                        except SQLAlchemyError as e:
                            print(f'Chain could not be updated: ', e)
                            db.session.rollback()
                        except Exception as e:
                            print(f'A problem occurred at receiving chain: ', e)
            except json.decoder.JSONDecodeError as e:
                # Handle the JSONDecodeError exception
                print("Failed to decode JSON:", str(e))
            except Exception as e:
                print(f'A problem occurred at receiving chain: ', e)

    # this is useless but for testing
    def tester_spitter(self):
        counter = 0
        while True:
            with self.app.app_context():
                print('Spitting...')
                counter += 1
                blockchain = Blockchain(self.app)
                self.broadcast(self.publisher, blockchain.get_blocks_as_list_of_dict(), topic='chain')
                time.sleep(30)


def create_kafka(app):
    return KafkaPeerToPeer(app)
