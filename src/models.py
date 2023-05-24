import json
import hashlib
import uuid

from datetime import datetime
from sqlalchemy.dialects.mysql import INTEGER
from fastecdsa import ecdsa, curve

from src import db


class Block(db.Model):

    __tablename__ = 'block'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    prev_hash = db.Column(db.String(1000), nullable=False)
    nonce = db.Column(INTEGER(unsigned=True), nullable=False)
    data = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.String(50), default=datetime.utcnow(), nullable=False)
    hash = db.Column(db.String(1000), nullable=False)

    def __init__(self, prev_hash: str = '000000000', nonce: int = 456,
                 data: str = '', timestamp: datetime = datetime.utcnow()) -> None:
        """
        :param timestamp: Must be given as a UTC value
        """
        self.prev_hash = prev_hash
        self.nonce = nonce
        self.data = data
        self.timestamp = timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
        self.hash = 'non-hashed'

    def encode_block(self):
        json_string = json.dumps(self, default=str, sort_keys=True).encode()
        new_hash = hashlib.sha256(json_string).hexdigest()
        self.hash = new_hash

    def as_dict(self):
        return {c.name: str(getattr(self, c.name)) for c in self.__table__.columns}

    def __repr__(self):
        return f'Block id: {self.id}, prev_hash: {self.prev_hash}, nonce: {self.nonce}, ' \
               f'timestamp: {self.timestamp}, hash: {self.hash}, data: {self.data}'


class Transaction(db.Model):
    __tablename__ = 'transaction'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    public_key = db.Column(db.String(1000), nullable=False)
    transaction_data_string = db.Column(db.String(1000), nullable=False)
    signature = db.Column(db.String(1000), nullable=False)
    valid = db.Column(db.Boolean(), default=False, nullable=False)

    def __init__(self, public_key=None, private_key=None, data=None):
        # Empty object to be filled afterwards
        if not public_key or not private_key or not data:
            self.public_key = ''
            self.transaction_data_string = ''
            self.signature = ''
            self.valid = False
        else:
            self.public_key = public_key
            transaction_data_dictionary = self.create_transaction_data_dictionary(data, datetime.utcnow())
            self.transaction_data_string = json.dumps(transaction_data_dictionary, sort_keys=True)
            signature = ecdsa.sign(self.transaction_data_string, private_key, curve=curve.secp256k1,
                                   hashfunc=ecdsa.sha256)
            self.signature = json.dumps(signature)
            self.valid = ecdsa.verify(signature, self.transaction_data_string, public_key, curve.secp256k1, ecdsa.sha256)

    @staticmethod
    def create_transaction_data_dictionary(data, timestamp=datetime.utcnow()):
        an_uuid = uuid.uuid4()
        transaction_id = str(an_uuid).replace('-', '')
        timestamp = timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
        transaction_data_dictionary = dict()
        transaction_data_dictionary["transaction_id"] = transaction_id
        transaction_data_dictionary["timestamp"] = timestamp
        transaction_data_dictionary["data"] = data
        return transaction_data_dictionary

    def as_dict(self):
        return {c.name: str(getattr(self, c.name)) for c in self.__table__.columns}

    def __repr__(self):
        return f'Transaction id: {self.id}, public_key: {self.public_key}, signature: {self.signature}, ' \
               f'transaction_data_dictionary: {self.transaction_data_string}'


class Node(db.Model):
    __tablename__ = 'node'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    address = db.Column(db.String(255), nullable=False)

    def __init__(self, address):
        self.address = address

    def as_dict(self):
        return {c.name: str(getattr(self, c.name)) for c in self.__table__.columns}

    def __repr__(self):
        return f'Node id: {self.id}, address: {self.address}'
