class FactoryPeerToPeer:

    registry: dict = dict()

    @classmethod
    def register(cls, _type: str, _creator):
        cls.registry[_type] = _creator

    @classmethod
    def create(cls, app, _type: str):
        creator = cls.registry.get(_type)
        if creator:
            return creator(app)
        else:
            raise ValueError(f"Invalid communication backend {_type}")
