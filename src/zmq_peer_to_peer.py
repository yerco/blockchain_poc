import json
import time
import zmq

from fastecdsa import ecdsa, curve
from fastecdsa.point import Point
from sqlalchemy.exc import SQLAlchemyError
from typing import Union

from src import db
from src.models import Block, Node, Transaction
from src.blockchain import Blockchain
from src.peer_to_peer import PeerToPeer
from src.zmqpublisher import ZMQPublisher


class ZMQPeerToPeer(PeerToPeer):
    _instance = None
    node_sub_sockets = []
    chain_sub_sockets = []
    transaction_sub_sockets = []
    poller = zmq.Poller()
    context = zmq.Context()
    num_of_publishers = 0
    num_of_subscribers = 0

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, app):
        super().__init__(app)
        self.broadcast_nodes_port = app.config['NODES_PORT']
        self.broadcast_transaction_port = app.config['TRANSACTION_PORT']
        self.broadcast_chain_port = app.config['CHAIN_PORT']
        self.node_publisher = self.set_publisher(self.broadcast_nodes_port)
        self.chain_publisher = self.set_publisher(self.broadcast_chain_port)
        self.transaction_publisher = self.set_publisher(self.broadcast_transaction_port)

    def bootstrap(self, *args, **kwargs):
        blockchain = Blockchain(self.app)
        first_node = Node(address=self.app.config['FIRST_NODE'])
        this_node = Node(address=self.app.config['THIS_NODE'])
        self.add_node(this_node)
        self.subscribe_to_node(this_node)
        if first_node.address != this_node.address:
            self.add_node(first_node)
            if self.subscribe_to_node(first_node) is False:
                # maybe wipe out the node table?
                self.remove_node(first_node)
                self.remove_node(this_node)
                print('Could not subscribe to first node, find another alternative as first node.')
                exit(0)
            # here this node informs the first node that it exists
            if blockchain.add_node_at(first_node, this_node) is False:
                print('Could not post to first node, find another alternative as first node.')
                exit(0)
            else:
                available_nodes = blockchain.get_nodes_from(first_node)
                registered_nodes = Node.query.all()
                _registered_nodes = []
                for registered_node in registered_nodes:
                    _registered_nodes.append(registered_node.as_dict())
                for node in available_nodes:
                    if node['address'] != self.app.config['THIS_NODE'] and not any(node['address'] in d.values() for d in _registered_nodes):
                        _node = Node(address=node['address'])
                        _node.id = node['id']
                        self.subscribe_to_node(_node)
                        self.add_node(_node)

                    # at least get a genesis block
                    if not Block.query.all():
                        response = blockchain.get_blocks_from(Node(address=node['address']), 1)
                        if response:
                            try:
                                genesis_block = Block()
                                [setattr(genesis_block, key, response[key]) for key in response]
                                db.session.add(genesis_block)
                                db.session.commit()
                            except SQLAlchemyError as e:
                                print(f'Genesis block could not be added: ', e)
                            except Exception as e:
                                print(f'A problem occurred while adding the genesis block: ', e)
        else:
            # this node could be the first of all
            if blockchain.create_genesis_block():
                print('Genesis block created.')
            else:
                print('Genesis block already exists.')

    def subscribe_to_node(self, node: Node) -> bool:
        try:
            node_subscriber = self.set_subscriber(node.address, self.broadcast_nodes_port)
            self.node_sub_sockets.append(node_subscriber)
            self.poller.register(node_subscriber, zmq.POLLIN)
            self.num_of_subscribers += 1
            chain_subscriber = self.set_subscriber(node.address, self.broadcast_chain_port)
            self.chain_sub_sockets.append(chain_subscriber)
            self.poller.register(chain_subscriber, zmq.POLLIN)
            self.num_of_subscribers += 1
            transaction_subscriber = self.set_subscriber(node.address, self.broadcast_transaction_port)
            self.transaction_sub_sockets.append(transaction_subscriber)
            self.poller.register(transaction_subscriber, zmq.POLLIN)
            self.num_of_subscribers += 1
            return True
        except zmq.error.ZMQError as e:
            print(f'Node: {self.app.config["THIS_NODE"]} could not be subscribed to {node.address}', e)
            return False
        except Exception as e:
            print(f'Node: {self.app.config["THIS_NODE"]} could not be subscribed to {node.address}', e)
            return False

    def set_publisher(self, port):
        try:
            publisher = ZMQPublisher(port)
            print(f'Publisher broadcasting at: tcp://*:{port}')
            self.num_of_publishers += 1
            return publisher
        except zmq.error.ZMQError as e:
            raise e
        except Exception as e:
            print('Problem at set_publisher: ', e)

    def set_subscriber(self, address, port) -> Union[zmq.Socket, Exception]:
        try:
            subscriber = self.context.socket(zmq.SUB)
            subscriber.connect(f'tcp://{address}:{port}')
            subscriber.setsockopt_string(zmq.SUBSCRIBE, '')
            print(f'Node {self.app.config["THIS_NODE"]} subscribed to {address} ready on port: {port}')
            return subscriber
        except zmq.error.ZMQError as e:
            raise e
        except Exception as e:
            print('Problem at set_subscriber: ', e)

    def broadcast(self, publisher, data, topic=None) -> bool:
        try:
            _data = json.dumps(data, sort_keys=True, ensure_ascii=False)
            publisher.send_json(_data)
            print(f'Just broadcast: {_data}')
            return True
        except Exception as e:
            print(f'Problems broadcasting: ', e)
            return False

    def receive_transaction(self):
        socks = dict(self.poller.poll(1000))

        for transaction_sub_socket in self.transaction_sub_sockets:
            try:
                if transaction_sub_socket in socks:
                    transaction: dict = json.loads(transaction_sub_socket.recv_json())
                    if transaction['id'] != 'None':
                        transaction_id = transaction['id']
                    else:
                        transactions = Transaction.query.all()
                        transaction_id = len(transactions) + 1
                    received_public_key = transaction['public_key'].split(' ')
                    x = int(received_public_key[1].strip()[:-2], 16)
                    y = int(received_public_key[2].strip()[:-4], 16)
                    public_key = Point(x, y, curve=curve.secp256k1)
                    transaction_data_string = transaction['transaction_data_string']
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
                                self.broadcast(self.chain_publisher, blockchain.get_blocks_as_list_of_dict())
                                db.session.query(Transaction).delete()
                                db.session.commit()
                        except SQLAlchemyError as e:
                            print(f'Transaction {transaction_id} could not be added: ', e)
                            continue
                    else:
                        print(f'Transaction: {transaction_id} is not valid.')
            except zmq.ZMQError as e:
                # Handle the error
                print(f"ZMQError at receiving transaction: {e}")
            except Exception as e:
                print(f'Problem receiving transaction: ', e)
                continue

    def receive_node(self):
        socks = dict(self.poller.poll(1000))

        # Handle incoming messages from all subscribed sockets
        for node_sub_socket in self.node_sub_sockets:
            if node_sub_socket in socks:
                node: dict = json.loads(node_sub_socket.recv_json())
                received_node = Node(address=node['address'])
                if node['id'] != 'None':
                    received_node.id = node['id']
                else:
                    received_node.id = None
                print(f'{received_node.id}, {received_node.address} arrived to {self.app.config["THIS_NODE"]}')
                try:
                    existing_nodes = Node.query.filter_by(address=received_node.address).all()
                    if len(existing_nodes) >= 1:
                        Node.query.filter_by(address=received_node.address).delete()
                        db.session.commit()
                        db.session.add(received_node)
                        db.session.commit()
                        print(f'Broadcast node: there was at least one node with the same address: {received_node.address}')
                        # continue
                        # raise Exception(f'Broadcast node: there is at least one node with the same address: {received_node.address}')
                    # TODO check if it's necessary to swap the ids
                    # elif len(existing_node) == 1:
                    #     _nodes = Node.query.all()
                    #     existing_node.id = len(_nodes) + 1
                    #     db.session.add(received_node)
                    #     db.session.add(existing_node)
                    #     db.session.commit()
                    #     print(f'Node: {received_node.id}, {received_node.address} already registered.')
                    else:
                        # Fresh node
                        db.session.add(received_node)
                        db.session.commit()
                        print(f'Node: {received_node.id}, {received_node.address} added.')
                        self.subscribe_to_node(received_node)
                        print(f'{self.app.config["THIS_NODE"]} subscribed to {received_node.address}')
                except SQLAlchemyError as e:
                    # TODO make it more elegant instead of just spit the exception
                    print(f'Node {received_node.id}, {received_node.address} could not be added: ', e)
                    db.session.rollback()
                except Exception as e:
                    print(f'A problem occurred ', e)
                    # raise Exception(f'A problem occurred ', e)

    def receive_chain(self):
        socks = dict(self.poller.poll(1000))

        try:
            # Handle incoming messages from all subscribed sockets
            for chain_sub_socket in self.chain_sub_sockets:
                if chain_sub_socket in socks:
                    received_blocks = json.loads(chain_sub_socket.recv_json())
                    stored_blocks = Block.query.all()
                    if len(received_blocks) > len(stored_blocks):
                        # first we check the received blocks against what we already have
                        for i in range(len(stored_blocks)):
                            if stored_blocks[i].as_dict() != received_blocks[i]:
                                print(f'Inconsistency in the chain received compared with the one we already have')
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
                            print(f'Chain updated and broadcast.')
                            self.broadcast(self.chain_publisher, received_blocks)
                            # TODO: delete only required, here we are wiping out everything
                            db.session.query(Transaction).delete()
                            db.session.commit()
                        except SQLAlchemyError as e:
                            print(f'Chain could not be updated: ', e)
                            db.session.rollback()
        except zmq.ZMQError as e:
            # Handle the error
            print(f"ZMQError at receiving chain: {e}")
        except Exception as e:
            print(f'A problem occurred receiving chain: ', e)

    def add_node(self, node: Node) -> bool:
        if node.address != self.app.config['THIS_NODE']:
            try:
                nodes = Node.query.all()
                for _node in nodes:
                    if _node.address == node.address:
                        print(f'Node: {node.id}, {node.address} already exists in {self.app.config["THIS_NODE"]}.')
                        return False
                id_taker = Node.query.filter_by(id=node.id).first()
                if id_taker is not None:
                    node.id = len(nodes) + 1
                db.session.add(node)
                db.session.commit()
                print(f'Node: {node.id}, {node.address} has been added in {self.app.config["THIS_NODE"]}.')
                return True
            except SQLAlchemyError as e:
                print(f'Node {node} could not be added: ', e)
                return False
            except Exception as e:
                print(f'A problem occurred while adding node {node}: ', e)
                return False
        else:
            # node could have been reset (it still at the database)
            nodes = Node.query.all()
            for _node in nodes:
                if _node.address == node.address:
                    print(f'Node: {node.id}, {node.address} already exists in {self.app.config["THIS_NODE"]}.')
                    return False
            # adding THIS node to the database
            db.session.add(node)
            db.session.commit()
            print(f'THIS node: {node.id}, {node.address} added to itself DB.')
            return True

    def remove_node(self, node: Node) -> bool:
        try:
            db.session.delete(node)
            db.session.commit()
            print(f'Node: {node.id}, {node.address} has been removed from {self.app.config["THIS_NODE"]}.')
            return True
        except SQLAlchemyError as e:
            print(f'Node {node} could not be removed: ', e)
            return False
        except Exception as e:
            print(f'A problem occurred while removing node {node}: ', e)
            return False

    # this is useless but for testing
    def tester_spitter(self):
        counter = 0
        with self.app.app_context():
            while True:
                print('Spitter')
                counter += 1
                last_octet = int(self.app.config['THIS_NODE'].split('.')[-1])
                address = f'{last_octet}.0.0.{counter}'
                node = Node(address=address)
                self.broadcast(self.node_publisher, node.as_dict())
                time.sleep(15)


def create_zmq(app):
    return ZMQPeerToPeer(app)
