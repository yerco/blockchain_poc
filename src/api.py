import os

from flask import Blueprint, request, current_app
from flask_restx import Resource, Api, fields
from fastecdsa.keys import import_key

from src import db
from src.blockchain import Blockchain
from src.models import Block, Node, Transaction
from src.factory_peer_to_peer import FactoryPeerToPeer
from src.kafka_peer_to_peer import create_kafka
from src.zmq_peer_to_peer import create_zmq

api_blueprint = Blueprint('api', __name__)
api = Api(api_blueprint)

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
        if current_app.config['COMM'] == 'zmq':
            db.session.add(transaction)
            db.session.commit()
            peer_to_peer.broadcast(peer_to_peer.transaction_publisher, transaction.as_dict())
            transactions = Transaction.query.all()
            # for zmq we start mining here immediately
            # check if the number of transactions is equal to the number of transactions that can be mined
            if len(transactions) >= current_app.config['TRANSACTIONS_AMOUNT']:
                # start the mining process
                blockchain = Blockchain(current_app)
                # done sequentially, TODO: do it in parallel otherwise the POST can be hung for a long time
                block = blockchain.proof_of_work()
                # add the block to the blockchain
                db.session.add(block)
                db.session.commit()
                blocks = blockchain.get_blocks_as_list_of_dict()
                peer_to_peer.broadcast(peer_to_peer.chain_publisher, blocks)
                db.session.query(Transaction).delete()
                db.session.commit()
        else:
            peer_to_peer.broadcast(peer_to_peer.publisher, transaction.as_dict(), topic='transaction')

        response_object = {
            'message': f'{transaction.transaction_data_string}'
        }
        return response_object, 201

    @api.marshal_with(transaction_model, as_list=True)
    def get(self):
        return Transaction.query.all(), 200


api.add_resource(TransactionsList, '/transactions')


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
            print(f'{sender_ip_address} is asking to add node {address}')
        if address != current_app.config['THIS_NODE']:
            nodes = Node.query.all()
            for node in nodes:
                if node.address == address:
                    return {'message': f'{current_app.config["THIS_NODE"]} already knows {address}!'}, 400
            new_node = Node(address)
            new_node.id = len(nodes) + 1
            peer_to_peer = FactoryPeerToPeer.create(current_app, current_app.config['COMM'])
            blockchain = Blockchain(current_app)
            if blockchain.add_node(new_node):
                peer_to_peer.subscribe_to_node(new_node)
                # the node was added successfully, we publish it to the other nodes
                if current_app.config['COMM'] == 'zmq':
                    peer_to_peer.broadcast(peer_to_peer.node_publisher, new_node.as_dict())
                    peer_to_peer.broadcast(peer_to_peer.node_publisher, new_node.as_dict())
                    peer_to_peer.broadcast(peer_to_peer.node_publisher, new_node.as_dict())
                else:
                    peer_to_peer.broadcast(peer_to_peer.publisher, new_node.as_dict(), topic='node')
                return {'message': f'{current_app.config["THIS_NODE"]} now knows node {address}!'}, 200
            else:  # something happened at database level
                return {'message': f'node {address} could not be added, Database error!'}, 500
        else:
            return {'message': f'{address} sent a request to itself {current_app.config["THIS_NODE"]}!!!'}, 400

    @api.marshal_with(node_model, as_list=True)
    def get(self):
        return Node.query.all(), 200


api.add_resource(NodesList, '/nodes')


# node resource
block_model = api.model('Node', {
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
            api.abort(404, f'Block {block_id} not found')
        return block, 200


api.add_resource(Blocks, '/blocks/<int:block_id>')


class BlocksList(Resource):

    @api.marshal_with(block_model, as_list=True)
    def get(self):
        return Block.query.all(), 200


api.add_resource(BlocksList, '/blocks')
