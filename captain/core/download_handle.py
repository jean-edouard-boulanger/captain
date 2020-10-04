from typing import Union
import uuid


class DownloadHandle:
    handle: uuid.UUID

    def __init__(self, handle: Union[uuid.UUID, str]):
        if isinstance(handle, uuid.UUID):
            self.handle = handle
        if isinstance(handle, str):
            self.handle = uuid.UUID(handle)

    def __str__(self):
        return str(self.handle)

    def __repr__(self):
        return f"DownloadHandle({self.handle})"

    def __hash__(self):
        return hash(self.handle)

    def __eq__(self, other: 'DownloadHandle'):
        return self.handle == other.handle

    @staticmethod
    def make() -> 'DownloadHandle':
        return DownloadHandle(uuid.uuid4())
