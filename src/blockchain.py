import asyncio
import hashlib
import json

from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

from src import db
from src.models import Block, Node, Transaction
from src.utilities import Utilities


class Blockchain:
    def __init__(self, app):
        self.app = app

    def create_genesis_block(self) -> bool:
        if self.app.config['FIRST_NODE'] == self.app.config['THIS_NODE']:
            blocks = Block.query.all()
            if len(blocks) == 0:
                timestamp = datetime.utcnow()
                data = 'This is the genesis block'
                # timestamp is cast to string inside Block init
                block = Block(prev_hash='000000000', nonce=456, data=data, timestamp=timestamp)
                block.encode_block()
                db.session.add(block)
                db.session.commit()
                return True
            return False
        return False

    def proof_of_work(self) -> Block:
        verified_transactions = []
        transactions = Transaction.query.all()
        for transaction in transactions:
            verified_transactions.append(transaction.as_dict())
        verified_transactions_str = json.dumps(verified_transactions, sort_keys=True)

        timestamp = datetime.utcnow()
        last_block = Block.query.order_by(Block.id.desc()).first()
        block = Block(prev_hash=last_block.hash, nonce=456, data=verified_transactions_str, timestamp=timestamp)
        block.id = last_block.id + 1

        mining = False
        while mining is False:
            block.encode_block()
            new_hash = hashlib.sha256(json.dumps(block.as_dict(), sort_keys=True, ensure_ascii=False).encode()).hexdigest()

            if new_hash[:len(self.app.config['NONCE_ZEROES'])] == self.app.config['NONCE_ZEROES']:
                mining = True
            else:
                block.nonce += 1
                block.encode_block()
                new_hash = hashlib.sha256(json.dumps(block.as_dict(), sort_keys=True, ensure_ascii=False).encode()).hexdigest()

        print(f'\n\n\nNew block mined: {new_hash}\n\n\n')
        block.hash = new_hash
        return block

    def get_blocks_as_list_of_dict(self):
        blocks = Block.query.all()
        _blocks = []
        for block in blocks:
            _blocks.append(block.as_dict())
        return _blocks

    def get_blocks_from(self, node: Node, block_id=None):
        if not block_id:
            url = f'http://{node.address}:{self.app.config["FLASK_RUN_PORT"]}/blocks'
            result = asyncio.run(Utilities().make_get(url))
        else:
            url = f'http://{node.address}:{self.app.config["FLASK_RUN_PORT"]}/blocks/{block_id}'
            result = asyncio.run(Utilities().make_get(url))
        if result:
            print(f'Result of getting block (or blocks) from {node.address}: {result}')
            return result
        else:
            print('Something nasty happened.')
            return None

    def add_node_at(self, target_node: Node, new_node: Node) -> bool:
        url = f'http://{target_node.address}:{self.app.config["FLASK_RUN_PORT"]}/nodes'
        data = {'node_address': new_node.address}
        result = asyncio.run(Utilities().make_post(url, data))
        if result:
            print(f'Result of adding {new_node} in {target_node.address}: {result["message"]}')
            return True
        else:
            print('Something nasty happened.')
            return False

    def get_nodes_from(self, node: Node):
        url = f'http://{node.address}:{self.app.config["FLASK_RUN_PORT"]}/nodes'
        result = asyncio.run(Utilities().make_get(url))
        if result:
            print(f'Result of getting nodes from {node.address}: {result}')
            return result
        else:
            print('Something nasty happened.')
            return False
