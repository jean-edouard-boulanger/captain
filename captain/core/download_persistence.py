from .logging import get_logger
from .download_entities import DownloadHandle, DownloadEntry

import orjson

import sqlite3

from typing import Protocol, Dict, List, Optional, ContextManager
from contextlib import contextmanager
from pathlib import Path
import enum
import json
import traceback


logger = get_logger()


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
    def scoped_entry(self, handle: DownloadHandle) -> ContextManager[DownloadEntry]:
        try:
            entry = self.get_entry(handle)
            yield entry
            self.persist_entry(entry)
        except Exception as e:
            logger.warning(
                f"swallowed exception in scoped persistence block, not persisting {handle}: {e}"
            )
            raise


class InMemoryPersistence(PersistenceBase):
    def __init__(self, database_file_path: Optional[str] = None):
        self._db: Dict[DownloadHandle, DownloadEntry] = dict()
        self._persist_file_path = (
            Path(database_file_path).expanduser() if database_file_path else None
        )
        if self._persist_file_path and self._persist_file_path.is_file():
            try:
                with self._persist_file_path.open() as df:
                    data: Dict = json.load(df)
                    self._db = {
                        DownloadHandle(handle_str): DownloadEntry.deserialize(
                            entry_data
                        )
                        for handle_str, entry_data in data.items()
                    }
            except Exception as e:
                self._db = {}
                logger.warning(
                    f"failed to load persisted state: {e}\n{traceback.format_exc()}"
                )

    def has_entry(self, handle: DownloadHandle) -> bool:
        return handle in self._db

    def get_entry(self, handle: DownloadHandle) -> DownloadEntry:
        if handle not in self._db:
            raise KeyError(f"unknown download handle: {handle}")
        return self._db[handle].clone()

    def get_all_entries(self) -> List[DownloadEntry]:
        return [entry.clone() for entry in self._db.values()]

    def remove_entry(self, handle) -> None:
        del self._db[handle]

    def persist_entry(self, entry: DownloadEntry) -> None:
        self._db[entry.handle] = entry

    def flush(self):
        if self._persist_file_path:
            with self._persist_file_path.open("w") as df:
                output = {
                    str(handle): entry.serialize() for handle, entry in self._db.items()
                }
                df.write(json.dumps(output, indent=4))


class SQLitePersistence(PersistenceBase):
    def __init__(self, database_file_path: str):
        self._conn = sqlite3.connect(
            str(Path(database_file_path).expanduser()), check_same_thread=False
        )
        self._conn.row_factory = SQLitePersistence._dict_factory
        self._init_db()

    def has_entry(self, handle: DownloadHandle) -> bool:
        cursor = self._cursor()
        cursor.execute(
            """
            SELECT COUNT(*) AS count FROM download_entries
             WHERE handle = :handle
        """,
            {"handle": str(handle)},
        )
        row = cursor.fetchone()
        return row["count"] == 1

    def get_entry(self, handle: DownloadHandle) -> DownloadEntry:
        cursor = self._cursor()
        cursor.execute(
            """
            SELECT payload FROM download_entries
             WHERE handle = :handle;
        """,
            {"handle": str(handle)},
        )
        row = cursor.fetchone()
        return DownloadEntry.deserialize(orjson.loads(row["payload"]))

    def get_all_entries(self) -> List[DownloadEntry]:
        cursor = self._cursor()
        cursor.execute("SELECT payload FROM download_entries")
        return [
            DownloadEntry.deserialize(orjson.loads(row["payload"])) for row in cursor
        ]

    def remove_entry(self, handle) -> None:
        cursor = self._cursor()
        cursor.execute(
            """
            DELETE FROM download_entries
             WHERE handle = :handle;
        """,
            {"handle": str(handle)},
        )

    def persist_entry(self, entry: DownloadEntry) -> None:
        cursor = self._cursor()
        cursor.execute(
            """
            INSERT INTO download_entries (handle, payload)
            VALUES (:handle, :payload)
            ON CONFLICT(handle) DO UPDATE SET payload = excluded.payload;
        """,
            {"handle": str(entry.handle), "payload": orjson.dumps(entry.serialize())},
        )

    def flush(self):
        pass

    def _cursor(self):
        return self._conn.cursor()

    @staticmethod
    def _dict_factory(cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def _init_db(self):
        self._cursor().execute(
            """
            CREATE TABLE IF NOT EXISTS download_entries (
                handle CHAR(36) PRIMARY KEY ,
                payload BLOB
            );
        """
        )


class PersistenceType(enum.Enum):
    IN_MEMORY = enum.auto()
    SQLITE = enum.auto()


def get_persistence(persistence_type: PersistenceType, **kwargs):
    if persistence_type == PersistenceType.IN_MEMORY:
        return InMemoryPersistence(**kwargs)
    if persistence_type == PersistenceType.SQLITE:
        return SQLitePersistence(**kwargs)
    raise KeyError(f"unsupported persistence type: {persistence_type}")
