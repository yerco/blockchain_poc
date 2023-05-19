import threading

from flask.cli import FlaskGroup
from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError

from src import create_app, db
from src.blockchain import Blockchain
from src.factory_peer_to_peer import FactoryPeerToPeer
from src.kafka_peer_to_peer import create_kafka
from src.zmq_peer_to_peer import create_zmq
from src.models import Block, Node

load_dotenv()

app = create_app()
app.app_context().push()

with app.app_context():
    db.create_all()
    db.session.commit()

blockchain = Blockchain(app)

FactoryPeerToPeer.register('zmq', create_zmq)
FactoryPeerToPeer.register('kafka', create_kafka)
peer_to_peer = FactoryPeerToPeer.create(app, app.config['COMM'])

# know yourself
this_node = Node(address=app.config['THIS_NODE'])
blockchain.add_node(this_node)
peer_to_peer.subscribe_to_node(this_node)
# know a first node
first_node = Node(address=app.config['FIRST_NODE'])
if first_node.address != this_node.address:
    blockchain.add_node(first_node)
    if peer_to_peer.subscribe_to_node(first_node) is False:
        # maybe wipe out the node table?
        blockchain.remove_node(first_node)
        blockchain.remove_node(this_node)
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
            if node['address'] != app.config['THIS_NODE'] and not any(node['address'] in d.values() for d in _registered_nodes):
                _node = Node(address=node['address'])
                _node.id = node['id']
                peer_to_peer.subscribe_to_node(_node)
                blockchain.add_node(_node)

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

t1 = threading.Thread(target=peer_to_peer.awaiting_received_node)
t2 = threading.Thread(target=peer_to_peer.awaiting_received_chain)
t3 = threading.Thread(target=peer_to_peer.awaiting_transaction_broadcast)
# thread exclusive for testing, heartbeat
# t4 = threading.Thread(target=peer_to_peer.tester_spitter, daemon=True)

t1.start()
t2.start()
t3.start()
# thread exclusive for testing, heartbeat
# t4.start()

cli = FlaskGroup(create_app=create_app, params={})


@cli.command('recreate_db')
def recreate_db():
    """Initializes the database"""
    db.drop_all()
    db.create_all()
    db.session.commit()


if __name__ == '__main__':
    cli()
