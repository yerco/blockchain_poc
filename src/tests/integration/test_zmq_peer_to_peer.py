import aiohttp
import json
import os
import pytest
import sys
import threading
import time
import zmq

from datetime import datetime
from fastecdsa.keys import import_key
from freezegun import freeze_time

from src.models import Block, Node, Transaction
from src.zmq_peer_to_peer import ZMQPeerToPeer
from src.zmqpublisher import ZMQPublisher


def test_peer_to_peer_object_init(test_app):
    peer_to_peer = ZMQPeerToPeer(test_app)
    assert peer_to_peer.broadcast_nodes_port == '20344'
    assert peer_to_peer.broadcast_transaction_port == '22344'
    assert peer_to_peer.broadcast_chain_port == '21344'
    assert isinstance(peer_to_peer.context, zmq.Context)
    assert 'zmq.Context()' in peer_to_peer.context.__repr__()
    print(peer_to_peer.node_publisher)
    assert isinstance(peer_to_peer.node_publisher, ZMQPublisher)
    peer_to_peer.node_publisher.close()


def test_subscribe_to_nodes(test_app, test_database):
    peer_to_peer = ZMQPeerToPeer(test_app)
    # creating a loop
    localhost = '127.0.0.1'
    localhost_node = Node(localhost)
    assert peer_to_peer.add_node(localhost_node) is True
    assert peer_to_peer.subscribe_to_node(localhost_node) is True
    assert peer_to_peer.num_of_subscribers == 3
    assert len(peer_to_peer.poller.sockets) == 3
    assert isinstance(peer_to_peer.poller.sockets[0][0], zmq.Socket)
    assert peer_to_peer.poller.sockets[0][1] == zmq.POLLIN
    assert peer_to_peer.poller.sockets[0][0].getsockopt(zmq.LINGER) == 0
    assert peer_to_peer.poller.sockets[0][0].getsockopt(zmq.RCVTIMEO) == -1
    assert peer_to_peer.poller.sockets[0][0].getsockopt(zmq.RCVHWM) == 1000
    assert peer_to_peer.poller.sockets[0][0].type == zmq.SUB
    # Define a function that will run in a separate thread to receive messages
    def receive():
        msg = peer_to_peer.poller.sockets[0][0].recv_json()
        assert msg == {"message": "Hello World!"}
        assert peer_to_peer.num_of_subscribers == 3
    # Start the receive function in a separate thread
    receive_thread = threading.Thread(target=receive)
    receive_thread.start()
    # Wait for the thread to start before publishing the message
    time.sleep(0.1)
    message = {"message": "Hello World!"}
    peer_to_peer.node_publisher.send_json(message)
    # Wait for the message to be received before cleaning up
    receive_thread.join()

    # Clean up the sockets
    peer_to_peer.node_publisher.close()
    peer_to_peer.poller.sockets[0][0].close()


def test_subscribe_to_nodes_could_not_subscribe(test_app, test_database, monkeypatch, capsys):
    peer_to_peer = ZMQPeerToPeer(test_app)
    localhost = '127.0.0.1'
    localhost_node = Node(localhost)

    def mock_connect():
        raise zmq.error.ZMQError()
    monkeypatch.setattr(zmq.Socket, "connect", mock_connect)

    assert peer_to_peer.add_node(localhost_node) is True
    assert peer_to_peer.subscribe_to_node(localhost_node) is False
    out, err = capsys.readouterr()
    assert f'Node: {test_app.config["THIS_NODE"]} could not be subscribed to {localhost_node.address}' in out
    assert peer_to_peer.num_of_subscribers == 0


def test_cannot_subscribe_to_itself(test_app, test_database, capsys):
    peer_to_peer = ZMQPeerToPeer(test_app)
    itself = Node(test_app.config['THIS_NODE'])
    assert peer_to_peer.add_node(itself) is True
    assert peer_to_peer.subscribe_to_node(itself) is False
    out, err = capsys.readouterr()
    assert f'THIS node: {itself.id}, {test_app.config["THIS_NODE"]} is trying to subscribe to itself!' in out
    assert peer_to_peer.num_of_subscribers == 0


def test_broadcast(test_app, test_database):
    # set all the publishers to be ready
    peer_to_peer = ZMQPeerToPeer(test_app)
    # this is indeed a loop for testing
    localhost = '127.0.0.1'
    localhost_node = Node(localhost)
    assert peer_to_peer.subscribe_to_node(localhost_node) is True
    # Define a function that will run in a separate thread to receive messages
    def receive():
        msg = json.loads(peer_to_peer.poller.sockets[0][0].recv_json())
        assert msg == {"message": "Hello World!"}
        assert peer_to_peer.num_of_subscribers == 1
    # Start the receive function in a separate thread
    receive_thread = threading.Thread(target=receive)
    receive_thread.start()
    # Wait for the thread to start before publishing the message
    time.sleep(0.1)
    message = {"message": "Hello World!"}
    peer_to_peer.broadcast(peer_to_peer.node_publisher, message)
    # Wait for the message to be received before cleaning up
    receive_thread.join()
    # Clean up the sockets and context
    peer_to_peer.node_publisher.close()
    peer_to_peer.poller.sockets[0][0].close()


def test_receive_node(test_app, test_database, monkeypatch):
    peer_to_peer = ZMQPeerToPeer(test_app)
    localhost = '127.0.0.1'
    localhost_node = Node(localhost)
    localhost_node.id = 1

    assert peer_to_peer.subscribe_to_node(localhost_node) is True

    receive_thread = threading.Thread(target=peer_to_peer.awaiting_received_node)
    receive_thread.start()
    # Wait for the thread to start before publishing the message
    time.sleep(0.1)

    peer_to_peer.broadcast(peer_to_peer.node_publisher, localhost_node.as_dict())

    # Wait for the message to be received before cleaning up

    receive_thread.join(1)
    nodes = Node.query.all()
    assert len(nodes) == 1

    print("Thread is alive: ", receive_thread.is_alive())

    peer_to_peer.node_publisher.close()
    peer_to_peer.chain_publisher.close()
    peer_to_peer.poller.sockets[0][0].close()
    # peer_to_peer.context.term()  # apparently this is not needed


@freeze_time("2012-01-01")
def test_receive_chain(test_app, test_database, monkeypatch):
    # setting up pub/sub
    peer_to_peer = ZMQPeerToPeer(test_app)
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

    assert peer_to_peer.subscribe_to_node(localhost_node) is True

    receive_thread = threading.Thread(target=peer_to_peer.awaiting_received_chain)
    receive_thread.start()
    # Wait for the thread to start before publishing the message
    time.sleep(0.1)

    # we broadcast the chain
    peer_to_peer.broadcast(peer_to_peer.chain_publisher, _blocks)

    # Wait for the message to be received before cleaning up
    receive_thread.join(1)

    blocks = Block.query.all()
    assert len(blocks) == 3
    assert blocks[0].id == 1
    assert blocks[2].prev_hash == blocks[1].hash

    peer_to_peer.node_publisher.close()
    peer_to_peer.chain_publisher.close()
    for socket in peer_to_peer.poller.sockets:
        socket[0].close()
    # peer_to_peer.context.term()  # apparently this is not needed


def test_broadcast_and_receive_transaction(test_app, test_database):
    peer_to_peer = ZMQPeerToPeer(test_app)
    localhost = '127.0.0.1'
    localhost_node = Node(localhost)
    localhost_node.id = 1

    assert peer_to_peer.subscribe_to_node(localhost_node) is True

    # get the path of the current file
    current_file_path = __file__
    # get the directory path
    current_directory_path = os.path.dirname(os.path.abspath(current_file_path))
    private_key, public_key = import_key(f'{current_directory_path}/../../../keys/private_key.pem')
    transaction = Transaction(private_key=private_key, public_key=public_key, data={'test': 'test'})
    transaction.id = 1

    receive_thread = threading.Thread(target=peer_to_peer.awaiting_transaction_broadcast)
    receive_thread.start()
    # Wait for the thread to start before publishing the message
    time.sleep(0.1)

    peer_to_peer.broadcast(peer_to_peer.transaction_publisher, transaction.as_dict())

    # Wait for the message to be received before cleaning up
    receive_thread.join(1)

    transactions = Transaction.query.all()
    assert len(transactions) == 1
    # received_message = peer_to_peer.transaction_subscriber.recv_string()
    # received_transaction: str = json.loads(received_message)
    # received_transaction_as_dict = json.loads(received_transaction)
    # assert received_transaction_as_dict == transaction.as_dict()
    # signature = tuple(json.loads(received_transaction_as_dict['signature']))
    # # to remove the "b'" and "'" from the string we use [2:-1]
    # transaction_data_string = received_transaction_as_dict['transaction_data_string'][2:-1]
    # valid = received_transaction_as_dict['valid']
    # assert bool(valid) is True  # they say it's true
    # valid_checking_with_local_key = ecdsa.verify(signature, transaction_data_string, public_key, curve.secp256k1,
    #                                              ecdsa.sha256)
    # assert valid_checking_with_local_key is True  # they say it's true I have the public key
    # separated_public_key = received_transaction_as_dict['public_key'].split(' ')
    # x = int(separated_public_key[1].strip()[:-2], 16)
    # y = int(separated_public_key[2].strip()[:-4], 16)
    # received_public_key = Point(x, y, curve=curve.secp256k1)
    # valid_checking_only_received_data = ecdsa.verify(signature, transaction_data_string, received_public_key,
    #                                                  curve.secp256k1, ecdsa.sha256)
    # assert valid_checking_only_received_data is True  # they say it's true I check with what they sent me

# def test_receive_transaction(test_app, test_database):
#     peer_to_peer = ZMQPeerToPeer(test_app)
#     # set all the publishers to be ready
#     node = Node('127.0.0.1')
#     # set all the subscribers to be ready
#     assert peer_to_peer.add_node(node) is True
#     current_file_path = __file__
#     current_directory_path = os.path.dirname(os.path.abspath(current_file_path))
#     private_key, public_key = import_key(f'{current_directory_path}/../../../keys/private_key.pem')
#     # this comes from the wire
#     transaction = Transaction(private_key=private_key, public_key=public_key, data={'test': 'test'})
#     transaction.id = 1
#     peer_to_peer.broadcast(peer_to_peer.transaction_publisher, transaction.as_dict())
#     assert peer_to_peer.receive_transaction() is True


# def test_receive_transaction_threshold_must_broadcast(test_app, test_database, monkeypatch):
#     # # setting us as the subscriber
#     # peer_to_peer = ZMQPeerToPeer(test_app)
#     # subscriber = peer_to_peer.set_subscriber(peer_to_peer.context, 'localhost', peer_to_peer.broadcast_transaction_port)
#     # # This TTL put here because otherwise the test will hang forever (if the whole file is run, separately works fine)
#     # subscriber.setsockopt(zmq.RCVTIMEO, 1000)
#     # monkeypatch.setattr(peer_to_peer, 'transaction_subscriber', subscriber)
#     peer_to_peer = ZMQPeerToPeer(test_app)
#     localhost = '127.0.0.1'
#     localhost_node = Node(localhost)
#     localhost_node.id = 1
#
#     assert peer_to_peer.subscribe_to_node(localhost_node) is True
#
#     current_file_path = __file__
#     current_directory_path = os.path.dirname(os.path.abspath(current_file_path))
#     private_key, public_key = import_key(f'{current_directory_path}/../../../keys/private_key.pem')
#
#     # we will have at least the genesis block
#     blockchain = Blockchain(test_app)
#     assert blockchain.create_genesis_block() is True
#
#     # we will set the amount of transactions to trigger at 4
#     test_app.config['TRANSACTIONS_AMOUNT'] = 4
#     # simple enough nonce for testing
#
#     test_app.config['NONCE_ZEROES'] = '0'
#     # we need 3 transactions
#     transaction1 = Transaction(private_key=private_key, public_key=public_key, data={'test': 'transaction1'})
#     transaction1.id = 1
#     transaction2 = Transaction(private_key=private_key, public_key=public_key, data={'test': 'transaction2'})
#     transaction2.id = 2
#     transaction3 = Transaction(private_key=private_key, public_key=public_key, data={'test': 'transaction3'})
#     transaction3.id = 3
#     db.session.add(transaction1)
#     db.session.add(transaction2)
#     db.session.add(transaction3)
#     db.session.commit()
#
#     receive_thread = threading.Thread(target=peer_to_peer.awaiting_transaction_broadcast)
#     receive_thread.start()
#     # Wait for the thread to start before publishing the message
#     time.sleep(0.1)
#
#     # the fourth should trigger the proof of work
#     transaction4 = Transaction(private_key=private_key, public_key=public_key, data={'test': 'transaction4'})
#     transaction4.id = 4
#
#     peer_to_peer.broadcast(peer_to_peer.transaction_publisher, transaction4.as_dict())
#
#     receive_thread.join(10)
#
#     # a block was mined
#     blocks = Block.query.all()
#     assert len(blocks) == 2
#     assert blocks[1].id == 2
