import sqlite3
from pathlib import Path
from typing import List, Literal

import orjson
from pydantic import BaseModel

from .domain import DownloadEntry, DownloadHandle
from .logging import get_logger
from .persistence import PersistenceBase
from .serialization import serialize, to_json

logger = get_logger()


class SQLitePersistence(PersistenceBase):
    class Settings(BaseModel):
        persistence_type: Literal["sqlite"] = "sqlite"
        database_file_path: str

    def __init__(self, settings: "SQLitePersistence.Settings"):
        self._conn = sqlite3.connect(
            settings.database_file_path
            if settings.database_file_path == ":memory:"
            else Path(settings.database_file_path).expanduser().absolute()
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
        return DownloadEntry.parse_obj(orjson.loads(row["payload"]))

    def get_all_entries(self) -> List[DownloadEntry]:
        cursor = self._cursor()
        cursor.execute("SELECT payload FROM download_entries")
        return [DownloadEntry.parse_obj(orjson.loads(row["payload"])) for row in cursor]

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
            {"handle": str(entry.handle), "payload": to_json(serialize(entry))},
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
