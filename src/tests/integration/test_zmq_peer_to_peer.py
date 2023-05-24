import json
import os
import pytest
import threading
import time
import zmq

from datetime import datetime
from fastecdsa.keys import import_key
from freezegun import freeze_time

from src import db
from src.blockchain import Blockchain
from src.models import Block, Node, Transaction
from src.zmqpublisher import ZMQPublisher


def test_peer_to_peer_object_init(test_zmq_peer_to_peer):
    assert test_zmq_peer_to_peer.broadcast_nodes_port == '20344'
    assert test_zmq_peer_to_peer.broadcast_transaction_port == '22344'
    assert test_zmq_peer_to_peer.broadcast_chain_port == '21344'
    assert isinstance(test_zmq_peer_to_peer.context, zmq.Context)
    assert 'zmq.Context()' in test_zmq_peer_to_peer.context.__repr__()
    assert isinstance(test_zmq_peer_to_peer.node_publisher, ZMQPublisher)
    test_zmq_peer_to_peer.node_publisher.close()


def test_subscribe_to_nodes(test_zmq_peer_to_peer, test_database):
    # creating a loop
    localhost = '127.0.0.1'
    localhost_node = Node(localhost)
    assert test_zmq_peer_to_peer.add_node(localhost_node) is True
    assert test_zmq_peer_to_peer.subscribe_to_node(localhost_node) is True
    assert test_zmq_peer_to_peer.num_of_subscribers == 3
    assert len(test_zmq_peer_to_peer.poller.sockets) == 3
    assert isinstance(test_zmq_peer_to_peer.poller.sockets[0][0], zmq.Socket)
    assert test_zmq_peer_to_peer.poller.sockets[0][1] == zmq.POLLIN
    assert test_zmq_peer_to_peer.poller.sockets[0][0].getsockopt(zmq.LINGER) == 0
    assert test_zmq_peer_to_peer.poller.sockets[0][0].getsockopt(zmq.RCVTIMEO) == -1
    assert test_zmq_peer_to_peer.poller.sockets[0][0].getsockopt(zmq.RCVHWM) == 1000
    assert test_zmq_peer_to_peer.poller.sockets[0][0].type == zmq.SUB
    # Define a function that will run in a separate thread to receive messages
    def receive():
        msg = test_zmq_peer_to_peer.poller.sockets[0][0].recv_json()
        assert msg == {"message": "Hello World!"}
        assert test_zmq_peer_to_peer.num_of_subscribers == 3
    # Start the receive function in a separate thread
    receive_thread = threading.Thread(target=receive)
    receive_thread.start()
    # Wait for the thread to start before publishing the message
    time.sleep(0.1)
    message = {"message": "Hello World!"}
    test_zmq_peer_to_peer.node_publisher.send_json(message)
    # Wait for the message to be received before cleaning up
    receive_thread.join(1)

    # Clean up the sockets
    test_zmq_peer_to_peer.node_publisher.close()
    test_zmq_peer_to_peer.poller.sockets[0][0].close()


def test_self_subscription(test_zmq_peer_to_peer, test_database, monkeypatch):
    localhost = '127.0.0.1'
    localhost_node = Node(localhost)

    def mock_connect():
        raise zmq.error.ZMQError()
    monkeypatch.setattr(zmq.Socket, "connect", mock_connect)

    assert test_zmq_peer_to_peer.add_node(localhost_node) is True
    assert test_zmq_peer_to_peer.subscribe_to_node(localhost_node) is True


def test_broadcasting(test_app, test_zmq_peer_to_peer, test_database):
    # this is indeed a loop for testing
    localhost = '127.0.0.1'
    localhost_node = Node(localhost)
    assert test_zmq_peer_to_peer.subscribe_to_node(localhost_node) is True
    # Define a function that will run in a separate thread to receive messages
    def receive():
        msg = json.loads(test_zmq_peer_to_peer.poller.sockets[0][0].recv_json())
        assert msg == {"message": "Hello World!"}
        assert test_zmq_peer_to_peer.num_of_subscribers == 1
    # Start the receive function in a separate thread
    receive_thread = threading.Thread(target=receive)
    receive_thread.start()
    # Wait for the thread to start before publishing the message
    time.sleep(0.1)
    message = {"message": "Hello World!"}
    test_zmq_peer_to_peer.broadcast(test_zmq_peer_to_peer.node_publisher, message)
    # Wait for the message to be received before cleaning up
    receive_thread.join()
    # Clean up the sockets and context
    test_zmq_peer_to_peer.node_publisher.close()
    test_zmq_peer_to_peer.poller.sockets[0][0].close()


def test_receive_node(test_zmq_peer_to_peer, test_database, monkeypatch):
    localhost = '127.0.0.1'
    localhost_node = Node(localhost)
    localhost_node.id = 1

    assert test_zmq_peer_to_peer.subscribe_to_node(localhost_node) is True

    receive_thread = threading.Thread(target=test_zmq_peer_to_peer.awaiting_received_node)
    receive_thread.start()
    # Wait for the thread to start before publishing the message
    time.sleep(0.1)

    test_zmq_peer_to_peer.broadcast(test_zmq_peer_to_peer.node_publisher, localhost_node.as_dict())

    # Wait for the message to be received before cleaning up

    receive_thread.join(1)
    nodes = Node.query.all()
    assert len(nodes) == 1

    print("Thread is alive: ", receive_thread.is_alive())
    receive_thread.join(1)
    test_zmq_peer_to_peer.node_publisher.close()
    test_zmq_peer_to_peer.chain_publisher.close()
    test_zmq_peer_to_peer.poller.sockets[0][0].close()
    # peer_to_peer.context.term()  # apparently this is not needed


@freeze_time("2012-01-01")
def test_receive_chain(test_zmq_peer_to_peer, test_database, monkeypatch):
    localhost = '127.0.0.1'
    localhost_node = Node(localhost)
    localhost_node.id = 1
    # we create a small chain
    block1 = Block(prev_hash='000000000', nonce=456, data='first block', timestamp=datetime.utcnow())
    block1.hash = 'firsthash'
    block1.id = 1
    block2 = Block(prev_hash='firsthash', nonce=456, data='second block', timestamp=datetime.utcnow())
    block2.hash = 'secondhash'
    block2.id = 2
    block3 = Block(prev_hash='secondhash', nonce=456, data='third block', timestamp=datetime.utcnow())
    block3.hash = 'third'
    block3.id = 3
    blocks = [block1, block2, block3]
    _blocks = []
    for block in blocks:
        _blocks.append(block.as_dict())

    assert test_zmq_peer_to_peer.subscribe_to_node(localhost_node) is True

    receive_thread = threading.Thread(target=test_zmq_peer_to_peer.awaiting_received_chain)
    receive_thread.start()
    # Wait for the thread to start before publishing the message
    time.sleep(0.1)

    # we broadcast the chain
    test_zmq_peer_to_peer.broadcast(test_zmq_peer_to_peer.chain_publisher, _blocks)

    # Wait for the message to be received before cleaning up
    receive_thread.join(1)

    blocks = Block.query.all()
    assert len(blocks) == 3
    assert blocks[0].id == 1
    assert blocks[2].prev_hash == blocks[1].hash

    test_zmq_peer_to_peer.node_publisher.close()
    test_zmq_peer_to_peer.chain_publisher.close()
    for socket in test_zmq_peer_to_peer.poller.sockets:
        socket[0].close()
    # peer_to_peer.context.term()  # apparently this is not needed


def test_add_node_itself(test_app, test_zmq_peer_to_peer, test_database, capsys):
    node = Node(test_app.config['THIS_NODE'])
    assert test_zmq_peer_to_peer.add_node(node) is True
    out, err = capsys.readouterr()
    assert f'THIS node: {node.id}, {test_app.config["THIS_NODE"]} added to itself DB.' in out
    assert Node.query.count() == 1


def test_add_pair_node(test_app, test_zmq_peer_to_peer, test_database, capsys):
    node = Node('1.2.3.4')
    assert test_zmq_peer_to_peer.add_node(node) is True
    assert Node.query.count() == 1
    out, err = capsys.readouterr()
    assert f'Node: {node.id}, {node.address} has been added in {test_app.config["THIS_NODE"]}' in out


def test_add_node_repeated_nodes(test_app, test_zmq_peer_to_peer, test_database, capsys):
    node = Node('1.2.3.4')
    assert test_zmq_peer_to_peer.add_node(node) is True
    assert Node.query.count() == 1
    out, err = capsys.readouterr()
    assert f'Node: {node.id}, {node.address} has been added in {test_app.config["THIS_NODE"]}' in out
    assert test_zmq_peer_to_peer.add_node(node) is False
    assert Node.query.count() == 1
    out, err = capsys.readouterr()
    assert f'Node: {node.id}, {node.address} already exists in {test_app.config["THIS_NODE"]}.' in out


@pytest.mark.timeout(2)
def test_broadcast_and_receive_transaction(test_app, test_zmq_peer_to_peer, test_database):
    localhost = '127.0.0.1'
    localhost_node = Node(localhost)
    localhost_node.id = 1

    assert test_zmq_peer_to_peer.subscribe_to_node(localhost_node) is True

    # get the path of the current file
    current_file_path = __file__
    # get the directory path
    current_directory_path = os.path.dirname(os.path.abspath(current_file_path))
    private_key, public_key = import_key(f'{current_directory_path}/../../../keys/private_key.pem')
    transaction = Transaction(private_key=private_key, public_key=public_key, data={'test': 'test'})
    transaction.id = 1

    def receive():
        with test_app.app_context():
            test_zmq_peer_to_peer.receive_transaction()

    receive_thread = threading.Thread(target=receive)
    receive_thread.start()
    # Wait for the thread to start before publishing the message
    time.sleep(0.1)

    test_zmq_peer_to_peer.broadcast(test_zmq_peer_to_peer.transaction_publisher, transaction.as_dict())

    # Wait for the message to be received before cleaning up
    receive_thread.join(1)

    transactions = Transaction.query.all()
    assert len(transactions) == 1
    print("Thread is alive: ", receive_thread.is_alive())


def test_receive_transaction_threshold_must_broadcast(test_app, test_zmq_peer_to_peer, test_database, monkeypatch):
    localhost = '127.0.0.1'
    localhost_node = Node(localhost)
    localhost_node.id = 1

    assert test_zmq_peer_to_peer.subscribe_to_node(localhost_node) is True

    current_file_path = __file__
    current_directory_path = os.path.dirname(os.path.abspath(current_file_path))
    private_key, public_key = import_key(f'{current_directory_path}/../../../keys/private_key.pem')

    # we will have at least the genesis block
    blockchain = Blockchain(test_app)
    assert blockchain.create_genesis_block() is True

    # we will set the amount of transactions to trigger at 4
    test_app.config['TRANSACTIONS_AMOUNT'] = 4
    # simple enough nonce for testing

    test_app.config['NONCE_ZEROES'] = '0'
    # we need 3 transactions
    transaction1 = Transaction(private_key=private_key, public_key=public_key, data={'test': 'transaction1'})
    transaction1.id = 1
    transaction2 = Transaction(private_key=private_key, public_key=public_key, data={'test': 'transaction2'})
    transaction2.id = 2
    transaction3 = Transaction(private_key=private_key, public_key=public_key, data={'test': 'transaction3'})
    transaction3.id = 3
    db.session.add(transaction1)
    db.session.add(transaction2)
    db.session.add(transaction3)
    db.session.commit()

    def receive():
        with test_app.app_context():
            test_zmq_peer_to_peer.receive_transaction()

    receive_thread = threading.Thread(target=receive)
    receive_thread.start()
    # Wait for the thread to start before publishing the message
    time.sleep(0.1)

    # the fourth should trigger the proof of work
    transaction4 = Transaction(private_key=private_key, public_key=public_key, data={'test': 'transaction4'})
    transaction4.id = 4

    test_zmq_peer_to_peer.broadcast(test_zmq_peer_to_peer.transaction_publisher, transaction4.as_dict())

    receive_thread.join(1)

    # a block was mined
    blocks = Block.query.all()
    assert len(blocks) == 2
    assert blocks[1].id == 2


@freeze_time("2012-01-01")
def test_broadcast_and_receive_chain(test_app, test_zmq_peer_to_peer, test_database):
    localhost = '127.0.0.1'
    localhost_node = Node(localhost)
    localhost_node.id = 1

    assert test_zmq_peer_to_peer.subscribe_to_node(localhost_node) is True

    block1 = Block(prev_hash='000000000', nonce=456, data='first block', timestamp=datetime.utcnow())
    block1.hash = 'firsthash'
    block1.id = 1
    block2 = Block(prev_hash='firsthash', nonce=456, data='second block', timestamp=datetime.utcnow())
    block2.hash = 'secondhash'
    block2.id = 2
    block3 = Block(prev_hash='secondhash', nonce=456, data='third block', timestamp=datetime.utcnow())
    block3.hash = 'third'
    block3.id = 3
    blocks = [block1, block2, block3]
    _blocks = []
    for block in blocks:
        _blocks.append(block.as_dict())

    def receive():
        with test_app.app_context():
            test_zmq_peer_to_peer.receive_chain()

    receive_thread = threading.Thread(target=receive)
    receive_thread.start()
    # Wait for the thread to start before publishing the message
    time.sleep(0.1)

    test_zmq_peer_to_peer.broadcast(test_zmq_peer_to_peer.chain_publisher, _blocks)

    # Wait for the message to be received before cleaning up
    receive_thread.join(1)

    the_blocks = Block.query.all()
    assert len(the_blocks) == 3
    print("Thread is alive: ", receive_thread.is_alive())
