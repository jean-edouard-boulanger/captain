from typing import Dict, List, Optional, Literal
from pathlib import Path
import json
import traceback

from pydantic import BaseModel

from .serialization import serialize, pretty_dump
from .persistence import PersistenceBase
from .logging import get_logger
from .domain import DownloadHandle, DownloadEntry

logger = get_logger()


class InMemoryPersistence(PersistenceBase):
    class Settings(BaseModel):
        persistence_type: Literal["in_memory"] = "in_memory"
        database_file_path: Optional[str] = None

    def __init__(self, settings: "InMemoryPersistence.Settings"):
        self._db: Dict[DownloadHandle, DownloadEntry] = dict()
        self._persist_file_path = (
            Path(settings.database_file_path).expanduser().absolute()
            if settings.database_file_path
            else None
        )
        if self._persist_file_path and self._persist_file_path.is_file():
            try:
                with self._persist_file_path.open() as df:
                    data: Dict = json.load(df)
                    self._db = {
                        DownloadHandle(handle=handle_str): DownloadEntry.parse_obj(
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
        return self._db[handle].copy(deep=True)

    def get_all_entries(self) -> List[DownloadEntry]:
        return [entry.copy(deep=True) for entry in self._db.values()]

    def remove_entry(self, handle) -> None:
        del self._db[handle]

    def persist_entry(self, entry: DownloadEntry) -> None:
        self._db[entry.handle] = entry

    def flush(self):
        if self._persist_file_path:
            with self._persist_file_path.open("w") as df:
                output = {
                    str(handle): serialize(entry) for handle, entry in self._db.items()
                }
                df.write(pretty_dump(output))
