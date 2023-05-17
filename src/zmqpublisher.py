import zmq


class ZMQPublisher:
    _instances = {}
    context = zmq.Context()

    def __new__(cls, port):
        if port not in cls._instances:
            instance = super().__new__(cls)
            instance.socket = cls.context.socket(zmq.PUB)
            instance.socket.bind(f'tcp://*:{port}')
            cls._instances[port] = instance
        return cls._instances[port]

    def send_json(self, data):
        self.socket.send_json(data)

    def close(self):
        self.socket.close()
