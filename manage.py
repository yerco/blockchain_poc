import threading

from flask.cli import FlaskGroup
from dotenv import load_dotenv

from src import create_app, db
from src.blockchain import Blockchain
from src.factory_peer_to_peer import FactoryPeerToPeer
from src.kafka_peer_to_peer import create_kafka
from src.zmq_peer_to_peer import create_zmq

load_dotenv()

app = create_app()
app.app_context().push()

with app.app_context():
    db.create_all()
    db.session.commit()

blockchain = Blockchain(app)

FactoryPeerToPeer.register('zmq', create_zmq)
FactoryPeerToPeer.register('kafka', create_kafka)
peer_to_peer = FactoryPeerToPeer.create(app, app.config['COMM'])
peer_to_peer.bootstrap()

t1 = threading.Thread(target=peer_to_peer.awaiting_received_node)
t2 = threading.Thread(target=peer_to_peer.awaiting_received_chain)
t3 = threading.Thread(target=peer_to_peer.awaiting_transaction_broadcast)

t1.start()
t2.start()
t3.start()

cli = FlaskGroup(create_app=create_app, params={})


@cli.command('recreate_db')
def recreate_db():
    """Initializes the database"""
    db.drop_all()
    db.create_all()
    db.session.commit()


if __name__ == '__main__':
    cli()
