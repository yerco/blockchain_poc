import os

from fastecdsa.keys import import_key
from flask import Blueprint, request, current_app
from flask_cors import CORS
from flask_restx import Resource, Api, fields
from http import HTTPStatus

from src.models import Block, Node, Transaction
from src.factory_peer_to_peer import FactoryPeerToPeer
from src.kafka_peer_to_peer import create_kafka
from src.zmq_peer_to_peer import create_zmq

api_blueprint = Blueprint('api', __name__)
api = Api(api_blueprint)
cors = CORS(api_blueprint, resources={r"*": {"origins": "*"}})

FactoryPeerToPeer.register('zmq', create_zmq)
FactoryPeerToPeer.register('kafka', create_kafka)


# transaction resource
transaction_api_model = api.model('Transaction', {
    'id': fields.Integer(readOnly=True),
    'full_names': fields.String(required=True),
    'practice_number': fields.String(required=True),
    'notes': fields.String(required=True)
})

transaction_model = api.model('Transaction', {
    'id': fields.Integer(readOnly=True),
    'public_key': fields.String(required=True),
    'transaction_data_string': fields.String(required=True),
    'signature': fields.String(required=True),
    'valid': fields.Boolean(required=True)
})


class TransactionsList(Resource):

    def __init__(self, api=None, *args, **kwargs):
        super().__init__(api, args, kwargs)
        # get the path of the current file
        current_file_path = __file__
        # get the directory path
        current_directory_path = os.path.dirname(os.path.abspath(current_file_path))
        self.private_key, self.public_key = import_key(f'{current_directory_path}/../keys/private_key.pem')

    @api.expect(transaction_api_model, validate=True)
    def post(self):
        post_data = request.get_json()
        full_names = post_data.get('full_names')
        practice_number = post_data.get('practice_number')
        notes = post_data.get('notes')
        data = {
            'full_names': full_names,
            'practice_number': practice_number,
            'notes': notes,
        }
        transaction = Transaction(public_key=self.public_key, private_key=self.private_key, data=data)
        peer_to_peer = FactoryPeerToPeer.create(current_app, current_app.config['COMM'])
        peer_to_peer.broadcast(peer_to_peer.transaction_publisher, transaction.as_dict(), topic='transaction')

        response_object = {
            'message': f'{transaction.transaction_data_string}'
        }
        return response_object, HTTPStatus.CREATED

    @api.marshal_with(transaction_model, as_list=True)
    def get(self):
        return Transaction.query.all(), HTTPStatus.OK


api.add_resource(TransactionsList, '/transactions')


class Transactions(Resource):

    @api.marshal_with(transaction_model)
    def get(self, transaction_id):
        block = Transaction.query.filter_by(id=transaction_id).first()
        if not block:
            api.abort(HTTPStatus.NOT_FOUND, f'Transaction {transaction_id} not found')
        return block, HTTPStatus.OK


api.add_resource(Transactions, '/transactions/<int:transaction_id>')

# node resource
node_model = api.model('Node', {
    'id': fields.Integer(readOnly=True),
    'address': fields.String(required=True),
})


class NodesList(Resource):
    def post(self):
        address = request.get_json().get('node_address')
        sender_ip_address = request.remote_addr
        # checking that the sender is who she says she is
        if sender_ip_address != address:
            print(f'Warning: {sender_ip_address} is asking to add node {address}')
        if address != current_app.config['THIS_NODE']:
            nodes = Node.query.all()
            for node in nodes:
                if node.address == address:
                    return {'message': f'{current_app.config["THIS_NODE"]} already knows {address}!'}, \
                           HTTPStatus.BAD_REQUEST
            new_node = Node(address)
            peer_to_peer = FactoryPeerToPeer.create(current_app, current_app.config['COMM'])
            peer_to_peer.broadcast(peer_to_peer.node_publisher, new_node.as_dict(), topic='node')
            return {'message': f'{current_app.config["THIS_NODE"]} now knows node {address}!'}, HTTPStatus.OK
        else:
            return {'message': f'{address} sent a request to itself {current_app.config["THIS_NODE"]}!!!'}, \
                   HTTPStatus.BAD_REQUEST

    @api.marshal_with(node_model, as_list=True)
    def get(self):
        return Node.query.all(), HTTPStatus.OK


api.add_resource(NodesList, '/nodes')


# node resource
block_model = api.model('Block', {
    'id': fields.Integer(readOnly=True),
    'prev_hash': fields.String(required=True),
    'nonce': fields.Integer(required=True),
    'data': fields.String(required=True),
    'timestamp': fields.String(required=True),
    'hash': fields.String(required=True),
})


class Blocks(Resource):

    @api.marshal_with(block_model)
    def get(self, block_id):
        block = Block.query.filter_by(id=block_id).first()
        if not block:
            api.abort(HTTPStatus.NOT_FOUND, f'Block {block_id} not found')
        return block, HTTPStatus.OK


api.add_resource(Blocks, '/blocks/<int:block_id>')


class BlocksList(Resource):

    @api.marshal_with(block_model, as_list=True)
    def get(self):
        return Block.query.all(), HTTPStatus.OK


api.add_resource(BlocksList, '/blocks')
