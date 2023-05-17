from abc import ABC, abstractmethod

from src.models import Node


class PeerToPeer(ABC):

    def __init__(self, app):
        self.app = app

    @abstractmethod
    def subscribe_to_node(self, node: Node) -> bool:
        raise NotImplementedError

    @abstractmethod
    def set_publisher(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def set_subscriber(self, address, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def broadcast(self, publisher, data, topic) -> bool:
        raise NotImplementedError

    @abstractmethod
    def receive_transaction(self):
        raise NotImplementedError

    def awaiting_transaction_broadcast(self):
        with self.app.app_context():
            while True:
                self.receive_transaction()

    @abstractmethod
    def receive_node(self):
        raise NotImplementedError

    def awaiting_received_node(self):
        with self.app.app_context():
            while True:
                self.receive_node()

    @abstractmethod
    def receive_chain(self):
        raise NotImplementedError

    def awaiting_received_chain(self):
        with self.app.app_context():
            while True:
                self.receive_chain()
