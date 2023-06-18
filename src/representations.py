class ModelAsDictMixin:

    def as_dict(self):
        return {c.name: str(getattr(self, c.name)) for c in self.__table__.columns}
