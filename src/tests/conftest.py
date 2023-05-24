import os
import signal

import pytest

from aiohttp import web
from aiohttp.test_utils import TestClient
from src import create_app, db
from src.kafka_peer_to_peer import KafkaPeerToPeer
from src.models import Transaction, Node
from src.zmq_peer_to_peer import ZMQPeerToPeer


@pytest.fixture(scope='function')
def test_app():
    app = create_app()
    app.config.from_object('src.config.TestingConfig')
    with app.app_context():
        yield app  # testing happens here


@pytest.fixture(scope='function')
def test_database():
    db.create_all()
    yield db  # testing happens here
    db.session.remove()
    db.drop_all()


@pytest.fixture(scope='function')
def add_transaction():
    def _add_transaction(public_key, private_key, data):
        transaction = Transaction(public_key=public_key, private_key=private_key, data=data)
        db.session.add(transaction)
        db.session.commit()
        return transaction
    return _add_transaction


@pytest.fixture(scope='function')
def add_node():
    def _add_node(address):
        node = Node(address)
        db.session.add(node)
        db.session.commit()
        return node
    return _add_node


@pytest.fixture(scope='function')
def test_kafka_peer_to_peer():
    app = create_app()
    app.config.from_object('src.config.TestingConfig')
    with app.app_context():
        peer_to_peer = KafkaPeerToPeer(app)
        yield peer_to_peer


@pytest.fixture(scope='function')
def test_zmq_peer_to_peer():
    app = create_app()
    app.config.from_object('src.config.TestingConfig')
    with app.app_context():
        peer_to_peer = ZMQPeerToPeer(app)
        yield peer_to_peer
