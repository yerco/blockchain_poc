import json
import os
import threading
import time
from datetime import datetime

from fastecdsa.keys import import_key
from freezegun import freeze_time

from src import db
from src.kafka_peer_to_peer import KafkaPeerToPeer
from src.models import Node, Transaction, Block


def test_kafka_producer(test_app, capsys):
    peer_to_peer = KafkaPeerToPeer(test_app)
    peer_to_peer.broadcast(peer_to_peer.publisher, json.dumps({"Chuck": "Schuldiner"}), topic="test01")
    out, err = capsys.readouterr()
    # Wait for the message to be delivered
    peer_to_peer.publisher.poll(1)   # Maximum time (1s) to block while waiting for events
    # Verify that the message was delivered successfully
    assert peer_to_peer.publisher.flush(1) == 0
    assert "Message produced: <cimpl.Message object at" in out


def test_kafka_receive_node(test_app, capsys):
    peer_to_peer = KafkaPeerToPeer(test_app)
    localhost = '127.0.0.1'
    localhost_node = Node(localhost)
    localhost_node.id = 1

    def produce():
        peer_to_peer.broadcast(peer_to_peer.publisher, localhost_node.as_dict(), topic="node")

    def consume():
        peer_to_peer.receive_node()

    producer_thread = threading.Thread(target=produce)
    consumer_thread = threading.Thread(target=consume)

    producer_thread.start()
    consumer_thread.start()

    producer_thread.join()
    consumer_thread.join()

    out, err = capsys.readouterr()
    assert f"Received: node {localhost_node.as_dict()}" in out


def test_kafka_receive_transaction(test_app, test_database, capsys):
    peer_to_peer = KafkaPeerToPeer(test_app)
    localhost = '127.0.0.1'
    localhost_node = Node(localhost)
    localhost_node.id = 1

    # get the path of the current file
    current_file_path = __file__
    # get the directory path
    current_directory_path = os.path.dirname(os.path.abspath(current_file_path))
    private_key, public_key = import_key(f'{current_directory_path}/../../../keys/private_key.pem')
    transaction = Transaction(private_key=private_key, public_key=public_key, data={'test': 'test'})
    transaction.id = 1

    def produce():
        peer_to_peer.broadcast(peer_to_peer.publisher, transaction.as_dict(), topic="transaction")

    def consume():
        peer_to_peer.receive_transaction()

    producer_thread = threading.Thread(target=produce)
    consumer_thread = threading.Thread(target=consume)

    producer_thread.start()
    consumer_thread.start()

    producer_thread.join()
    consumer_thread.join()

    out, err = capsys.readouterr()
    peer_to_peer.receive_transaction()
    assert f"Transaction: {transaction.id} added." in out

    transactions = Transaction.query.all()
    assert len(transactions) == 1
    assert transactions[0].signature == transaction.signature


@freeze_time("2012-01-01")
def test_kafka_receive_chain(test_app, test_database, monkeypatch, capsys):
    peer_to_peer = KafkaPeerToPeer(test_app)

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

    # counter = 0
    # def mock_broadcast_chain(self, publisher, blocks, topic):
    #     nonlocal counter
    #     counter += 1
    #     if counter == 2:
    #         return None
    #     return peer_to_peer.broadcast(peer_to_peer.publisher, block1.as_dict(), topic="chain")
    # monkeypatch.setattr(KafkaPeerToPeer, "broadcast", mock_broadcast_chain)

    def produce():
        peer_to_peer.broadcast(peer_to_peer.publisher, block1.as_dict(), topic="chain")

    def consume():
        peer_to_peer.receive_chain()

    producer_thread = threading.Thread(target=produce)
    consumer_thread = threading.Thread(target=consume)

    producer_thread.start()
    consumer_thread.start()

    producer_thread.join()
    consumer_thread.join()

    out, err = capsys.readouterr()
    peer_to_peer.receive_chain()
    #assert f"" in out

    blocks = Block.query.all()
    assert len(blocks) == 3
