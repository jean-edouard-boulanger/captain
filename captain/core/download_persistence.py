from .download_entities import (
    DownloadHandle,
    DownloadEntry
)

from typing import Protocol, Dict, List, Optional
from contextlib import contextmanager
from pathlib import Path
import enum
import json
import logging
import traceback


logger = logging.getLogger("persistence")


class PersistenceBase(Protocol):
    def has_entry(self, handle: DownloadHandle) -> bool:
        raise NotImplementedError("must implement 'has_entry'")

    def get_all_entries(self) -> List[DownloadEntry]:
        raise NotImplementedError("must implement 'get_all_entries'")

    def get_entry(self, handle: DownloadHandle) -> DownloadEntry:
        raise NotImplementedError("must implement 'get_entry'")

    def remove_entry(self, handle):
        raise NotImplementedError("must implement 'remove_entry'")

    def persist_entry(self, entry: DownloadEntry):
        raise NotImplementedError("must implement 'save_entry'")

    def flush(self):
        raise NotImplementedError("must implement 'flush'")

    @contextmanager
    def scoped_entry(self, handle: DownloadHandle):
        entry = self.get_entry(handle)
        yield entry
        self.persist_entry(entry)


class InMemoryPersistence(PersistenceBase):
    def __init__(self, persist_file_path: Optional[str] = None):
        self._db: Dict[DownloadHandle, DownloadEntry] = dict()
        self._persist_file_path = Path(persist_file_path).expanduser() if persist_file_path else None
        if self._persist_file_path and self._persist_file_path.is_file():
            try:
                with self._persist_file_path.open() as df:
                    data: Dict = json.load(df)
                    self._db = {
                        DownloadHandle(handle_str): DownloadEntry.deserialize(entry_data)
                        for handle_str, entry_data in data.items()
                    }
            except Exception as e:
                logger.warning(f"failed to load persisted state: {e}\n{traceback.format_exc()}")

    def has_entry(self, handle: DownloadHandle) -> bool:
        return handle in self._db

    def get_entry(self, handle: DownloadHandle) -> DownloadEntry:
        return self._db[handle]

    def get_all_entries(self) -> List[DownloadEntry]:
        return list(self._db.values())

    def remove_entry(self, handle):
        del self._db[handle]

    def persist_entry(self, entry: DownloadEntry):
        self._db[entry.handle] = entry

    def flush(self):
        if self._persist_file_path:
            with self._persist_file_path.open("w") as df:
                output = {
                    str(handle): entry.serialize()
                    for handle, entry in self._db.items()
                }
                df.write(json.dumps(output, indent=4))


class PersistenceType(enum.Enum):
    IN_MEMORY = enum.auto()


def get_persistence(persistence_type: PersistenceType, **kwargs):
    if persistence_type == PersistenceType.IN_MEMORY:
        return InMemoryPersistence(**kwargs)
    raise KeyError(f"unsupported persistence type: {persistence_type}")
