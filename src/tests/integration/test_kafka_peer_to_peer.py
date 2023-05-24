import json
import os
import threading
from datetime import datetime

from fastecdsa.keys import import_key
from freezegun import freeze_time

from src import db
from src.kafka_peer_to_peer import KafkaPeerToPeer
from src.models import Node, Transaction, Block


def test_kafka_producer(test_kafka_peer_to_peer, monkeypatch, capsys):
    # we need just one publisher for kafka
    assert test_kafka_peer_to_peer.publisher == test_kafka_peer_to_peer.node_publisher and \
           test_kafka_peer_to_peer.transaction_publisher == test_kafka_peer_to_peer.chain_publisher and \
           test_kafka_peer_to_peer.publisher == test_kafka_peer_to_peer.chain_publisher
    test_kafka_peer_to_peer.broadcast(test_kafka_peer_to_peer.publisher, json.dumps({"Chuck": "Schuldiner"}),
                                      topic="test01")
    out, err = capsys.readouterr()
    assert 'Broadcasting {"Chuck": "Schuldiner"} to topic test01' in out


def test_kafka_receive_node(test_kafka_peer_to_peer, monkeypatch, capsys):
    localhost = '127.0.0.1'
    localhost_node = Node(localhost)
    localhost_node.id = 1

    def mock_receive_node():
        print(f'Received: node {localhost_node.as_dict()} from partition')

    monkeypatch.setattr(test_kafka_peer_to_peer, 'receive_node', mock_receive_node)

    def produce():
        test_kafka_peer_to_peer.broadcast(test_kafka_peer_to_peer.publisher, localhost_node.as_dict(), topic="node")

    def consume():
        test_kafka_peer_to_peer.receive_node()

    producer_thread = threading.Thread(target=produce)
    consumer_thread = threading.Thread(target=consume)

    producer_thread.start()
    consumer_thread.start()

    producer_thread.join()
    consumer_thread.join()

    out, err = capsys.readouterr()
    assert f"Broadcasting {localhost_node.as_dict()} to topic node" in out
    assert f"Received: node {localhost_node.as_dict()} from partition" in out


def test_kafka_receive_transaction(test_app, test_kafka_peer_to_peer, test_database, monkeypatch, capsys):
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

    def mock_receive_transaction():
        print(f'Received: transaction {transaction.as_dict()} from partition')

    # mock the receive_transaction db action
    db.session.add(transaction)
    db.session.commit()

    monkeypatch.setattr(test_kafka_peer_to_peer, 'receive_transaction', mock_receive_transaction)

    def produce():
        test_kafka_peer_to_peer.broadcast(test_kafka_peer_to_peer.publisher, transaction.as_dict(), topic="transaction")

    def consume():
        with test_app.app_context():
            test_kafka_peer_to_peer.receive_transaction()

    producer_thread = threading.Thread(target=produce)
    consumer_thread = threading.Thread(target=consume)

    producer_thread.start()
    consumer_thread.start()

    producer_thread.join()
    consumer_thread.join()

    out, err = capsys.readouterr()
    assert f"Received: transaction {transaction.as_dict()} from partition" in out

    transactions = Transaction.query.all()
    assert len(transactions) == 1
    assert transactions[0].signature == transaction.signature


@freeze_time("2012-01-01")
def test_kafka_receive_chain(test_app, test_kafka_peer_to_peer, test_database, monkeypatch, capsys):
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

    counter = 0
    def mock_receive_chain():
        print(f'Received: chain {_blocks} from partition')

    # mock the receive_chain db action
    db.session.add(block1)
    db.session.add(block2)
    db.session.add(block3)
    db.session.commit()

    monkeypatch.setattr(test_kafka_peer_to_peer, 'receive_chain', mock_receive_chain)

    def produce():
        test_kafka_peer_to_peer.broadcast(test_kafka_peer_to_peer.publisher, _blocks, topic="chain")

    def consume():
        test_kafka_peer_to_peer.receive_chain()

    producer_thread = threading.Thread(target=produce)
    consumer_thread = threading.Thread(target=consume)

    producer_thread.start()
    consumer_thread.start()

    producer_thread.join()
    consumer_thread.join()

    out, err = capsys.readouterr()
    assert f"Broadcasting {_blocks} to topic chain" in out
    assert f"Received: chain {_blocks} from partition" in out

    blocks = Block.query.all()
    assert len(blocks) == 3
