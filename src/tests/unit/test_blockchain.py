import json
import os

from fastecdsa.keys import import_key
from freezegun import freeze_time

from src import db
from src.blockchain import Blockchain
from src.models import Block, Node, Transaction


class TestBlockchain:
    @freeze_time("2012-01-01")
    def test_create_genesis_block(self, test_app, test_database):
        blockchain = Blockchain(test_app)
        assert blockchain.create_genesis_block() is True
        blocks = Block.query.all()
        assert len(blocks) == 1
        print(blocks[0])
        assert blocks[0].id == 1
        assert blocks[0].prev_hash == '000000000'
        assert blocks[0].timestamp == '2012-01-01T00:00:00Z'
        assert blocks[0].hash == 'd51bba0d6febd2a463e4de79f43669c66a01561c0f9bec8975893162678d4924'
        assert blocks[0].data == 'This is the genesis block'

    def test_creating_blocks(self, test_app, test_database):
        blockchain = Blockchain(test_app)
        assert blockchain.create_genesis_block() is True
        block1_data = 'This is the first block after genesis'
        assert blockchain.create_and_store_new_block(block1_data) is True
        block2_data = 'This is the second block after genesis'
        assert blockchain.create_and_store_new_block(block2_data) is True
        block3_data = 'This is the third block after genesis'
        assert blockchain.create_and_store_new_block(block3_data) is True
        blocks = Block.query.all()
        assert len(blocks) == 4
        assert blocks[0].id == 1
        assert blocks[3].prev_hash == blocks[2].hash

    def test_proof_of_work(self, test_app, test_database):
        # first we create block and persist them to the database
        blockchain = Blockchain(test_app)
        test_app.config['FIRST_NODE'] = '1.2.3.4'
        test_app.config['THIS_NODE'] = '1.2.3.4'
        assert blockchain.create_genesis_block() is True
        block1_data = 'This is the first block after genesis'
        assert blockchain.create_and_store_new_block(block1_data) is True
        block2_data = 'This is the second block after genesis'
        assert blockchain.create_and_store_new_block(block2_data) is True
        block3_data = 'This is the third block after genesis'
        assert blockchain.create_and_store_new_block(block3_data) is True
        blocks = Block.query.all()
        assert len(blocks) == 4
        assert blocks[0].id == 1
        assert blocks[3].prev_hash == blocks[2].hash
        # then are supposed to have some queued transactions
        # get the path of the current file
        current_file_path = __file__
        # get the directory path
        current_directory_path = os.path.dirname(os.path.abspath(current_file_path))
        private_key, public_key = import_key(f'{current_directory_path}/../../../keys/private_key.pem')

        transaction1 = Transaction(private_key=private_key, public_key=public_key, data={'test1': 'test1'})
        transaction2 = Transaction(private_key=private_key, public_key=public_key, data={'test2': 'test2'})
        transaction3 = Transaction(private_key=private_key, public_key=public_key, data={'test3': 'test3'})
        db.session.add(transaction1)
        db.session.add(transaction2)
        db.session.add(transaction3)
        db.session.commit()

        # then we are supposed to mine the block
        new_block = blockchain.proof_of_work()
        assert new_block is not None
        assert new_block.prev_hash == blocks[3].hash
        chunk_of_transactions = [transaction1.as_dict(), transaction2.as_dict(), transaction3.as_dict()]
        assert chunk_of_transactions == json.loads(new_block.data)

    def test_add_node_itself(self, test_app, test_database, capsys):
        blockchain = Blockchain(test_app)
        node = Node(test_app.config['THIS_NODE'])
        assert blockchain.add_node(node) is True
        out, err = capsys.readouterr()
        assert f'THIS node: {node.id}, {test_app.config["THIS_NODE"]} added to itself DB.' in out
        assert Node.query.count() == 1
        # TODO remove
        # assert peer_to_peer.num_of_publishers == 3
        # assert peer_to_peer.num_of_subscribers == 0

    def test_add_pair_node(self, test_app, test_database, capsys):
        blockchain = Blockchain(test_app)
        node = Node('1.2.3.4')
        assert blockchain.add_node(node) is True
        assert Node.query.count() == 1
        out, err = capsys.readouterr()
        assert f'Node: {node.id}, {node.address} has been added in {test_app.config["THIS_NODE"]}' in out

    def test_add_node_repeated_nodes(self, test_app, test_database, capsys):
        # publishers will get ready
        blockchain = Blockchain(test_app)
        node = Node('1.2.3.4')
        assert blockchain.add_node(node) is True
        assert Node.query.count() == 1
        out, err = capsys.readouterr()
        assert f'Node: {node.id}, {node.address} has been added in {test_app.config["THIS_NODE"]}' in out
        assert blockchain.add_node(node) is False
        assert Node.query.count() == 1
        out, err = capsys.readouterr()
        assert f'Node: {node.id}, {node.address} already exists in {test_app.config["THIS_NODE"]}.' in out
        # TODO remove
        # assert peer_to_peer.num_of_publishers == 3
        # assert peer_to_peer.num_of_subscribers == 0
