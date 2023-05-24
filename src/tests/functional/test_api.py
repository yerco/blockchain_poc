import json
import os
import uuid

from fastecdsa.keys import import_key
from freezegun import freeze_time
from sqlalchemy.exc import SQLAlchemyError
from unittest.mock import patch

from src import db
from src.blockchain import Blockchain
from src.models import Block, Node, Transaction


@freeze_time("2012-01-01")
def test_add_transaction(test_app, test_database, monkeypatch):
    # Define the fixed UUID value that we want to mock
    fixed_uuid = uuid.UUID('00000000-0000-0000-0000-000000000000')
    # Define a function that always returns the fixed UUID value
    def mock_uuid4():
        return fixed_uuid
    # Monkeypatch the uuid.uuid4 function to use our mock function instead
    monkeypatch.setattr(uuid, 'uuid4', mock_uuid4)

    client = test_app.test_client()
    data_to_send = {
        'full_names': 'fullNames Test String',
        'practice_number': '1234567890',
        'notes': 'notes Test String ñandú',
    }
    resp = client.post(
        '/transactions',
        data=json.dumps(data_to_send),
        content_type='application/json',
    )
    data = json.loads(resp.data)
    message = json.loads(data['message'])
    assert resp.status_code == 201
    assert message['transaction_id'] == '00000000000000000000000000000000'
    assert message['timestamp'] == '2012-01-01T00:00:00Z'
    assert message['data'] == data_to_send


def test_add_transaction_invalid_json(test_app, test_database):
    client = test_app.test_client()
    resp = client.post(
        '/transactions',
        data=json.dumps({}),
        content_type='application/json',
    )
    data = json.loads(resp.data.decode())
    assert resp.status_code == 400
    assert 'Input payload validation failed' in data['message']


def test_add_transaction_invalid_json_keys(test_app, test_database):
    client = test_app.test_client()
    data_to_send = {
        'full_names': 'fullNames Test String',
    }
    resp = client.post(
        '/transactions',
        data=json.dumps(data_to_send),
        content_type='application/json',
    )
    data = json.loads(resp.data.decode())
    assert resp.status_code == 400
    assert 'Input payload validation failed' in data['message']


def test_get_transactions(test_app, test_database, add_transaction):
    # get the path of the current file
    current_file_path = __file__
    # get the directory path
    current_directory_path = os.path.dirname(os.path.abspath(current_file_path))
    private_key, public_key = import_key(f'{current_directory_path}/../../../keys/private_key.pem')
    data1 = {
        'full_names': 'fullNames Test String 1',
        'practice_number': '1234567890',
        'notes': 'notes Test String 1 ñandú'
    }
    add_transaction(public_key=public_key, private_key=private_key, data=data1)
    data2 = {
        'full_names': 'fullNames Test String 2',
        'practice_number': '0987654321',
        'notes': 'notes Test String 2 ñandú'
    }
    add_transaction(public_key=public_key, private_key=private_key, data=data2)
    client = test_app.test_client()
    resp = client.get('/transactions')
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert len(data) == 2
    assert data1 == json.loads(data[0]['transaction_data_string'])['data']
    assert data[0]['id'] == 1
    assert data[0]['valid'] is True
    assert data2 == json.loads(data[1]['transaction_data_string'])['data']
    assert data[1]['id'] == 2
    assert data[1]['valid'] is True

    resp = client.get('/transactions/1')
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert data['id'] == 1
    assert data1 == json.loads(data['transaction_data_string'])['data']


def test_getting_nodes(test_app, test_database):
    client = test_app.test_client()
    node1 = Node(address='1.2.3.4')
    node2 = Node(address='5.6.7.8')
    db.session.add(node1)
    db.session.add(node2)
    db.session.commit()
    resp = client.get('/nodes')
    data = json.loads(resp.data.decode())
    assert resp.status_code == 200
    assert len(data) == 2
    assert data[0]['address'] == '1.2.3.4'
    assert data[1]['address'] == '5.6.7.8'


def test_add_node_and_detect_duplicates(test_app, test_database, monkeypatch):
    client = test_app.test_client()
    localhost = '127.0.0.1'
    data_to_send = {
        'node_address': localhost
    }
    resp = client.post(
        '/nodes',
        data=json.dumps(data_to_send),
        content_type='application/json',
    )
    data = json.loads(resp.data)

    # mocking broadcast node successfully added
    db.session.add(Node(address=localhost))
    db.session.commit()

    assert data['message'] == f'{test_app.config["THIS_NODE"]} now knows node {localhost}!'
    assert resp.status_code == 200
    assert Node.query.count() == 1
    resp = client.post(
        '/nodes',
        data=json.dumps(data_to_send),
        content_type='application/json',
    )
    data = json.loads(resp.data.decode())
    assert data['message'] == f'{test_app.config["THIS_NODE"]} already knows {localhost}!'
    assert resp.status_code == 400
    assert Node.query.count() == 1


# Maybe if we use `request.remote_addr`
def test_add_node_address_of_sender_does_not_match_address_of_the_request(test_app, test_database, capsys):
    client = test_app.test_client()
    address = '1.2.3.4'
    data_to_send = {
        'node_address': address
    }
    resp = client.post(
        '/nodes',
        data=json.dumps(data_to_send),
        content_type='application/json',
    )
    localhost = '127.0.0.1'
    out, err = capsys.readouterr()
    assert f'{localhost} is asking to add node {address}' in out
    data = json.loads(resp.data.decode())
    assert data['message'] == f'{test_app.config["THIS_NODE"]} now knows node {address}!'
    assert resp.status_code == 200


def test_add_node_loop(test_app, test_database):
    data_to_send = {
        'node_address': test_app.config["THIS_NODE"]
    }
    with test_app.test_request_context(environ_base={'REMOTE_ADDR': test_app.config["THIS_NODE"]}):
        with test_app.test_client() as client:
            resp = client.post(
                '/nodes',
                data=json.dumps(data_to_send),
                content_type='application/json',
                environ_base={'REMOTE_ADDR': test_app.config["THIS_NODE"]}
            )
            data = json.loads(resp.data.decode())
    assert data['message'] == f'{test_app.config["THIS_NODE"]} sent a request to itself {test_app.config["THIS_NODE"]}!!!'
    assert resp.status_code == 400


def test_get_nodes(test_app, test_database):
    client = test_app.test_client()
    node1 = Node(address='1.2.3.4')
    node2 = Node(address='5.6.7.8')
    node3 = Node(address='9.10.11.12')
    db.session.add(node1)
    db.session.add(node2)
    db.session.add(node3)
    db.session.commit()
    resp = client.get('/nodes')
    data = json.loads(resp.data.decode())
    assert resp.status_code == 200
    assert len(data) == 3


def test_get_blocks(test_app, test_database):
    client = test_app.test_client()
    blockchain = Blockchain(test_app)
    test_app.config['FIRST_NODE'] = '1.2.3.4'
    test_app.config['THIS_NODE'] = '1.2.3.4'
    assert blockchain.create_genesis_block() is True
    assert len(Block.query.all()) == 1
    resp = client.get('/blocks')
    data = json.loads(resp.data.decode())
    assert data[0]['id'] == 1
    assert data[0]['prev_hash'] == '000000000'
    assert data[0]['data'] == 'This is the genesis block'
    assert resp.status_code == 200


def test_get_single_block(test_app, test_database):
    client = test_app.test_client()
    blockchain = Blockchain(test_app)
    test_app.config['FIRST_NODE'] = '1.2.3.4'
    test_app.config['THIS_NODE'] = '1.2.3.4'
    assert blockchain.create_genesis_block() is True
    assert len(Block.query.all()) == 1
    resp = client.get(f'/blocks/1')
    data = json.loads(resp.data.decode())
    assert resp.status_code == 200
    assert data['id'] == 1
    assert data['prev_hash'] == '000000000'
    assert data['data'] == 'This is the genesis block'
