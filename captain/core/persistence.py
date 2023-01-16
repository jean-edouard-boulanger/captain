from contextlib import contextmanager
from typing import ContextManager, Protocol

from .domain import DownloadEntry, DownloadHandle
from .logging import get_logger

logger = get_logger()


class PersistenceBase(Protocol):
    def has_entry(self, handle: DownloadHandle) -> bool:
        raise NotImplementedError("must implement 'has_entry'")

    def get_all_entries(self) -> list[DownloadEntry]:
        raise NotImplementedError("must implement 'get_all_entries'")

    def get_entry(self, handle: DownloadHandle) -> DownloadEntry:
        raise NotImplementedError("must implement 'get_entry'")

    def remove_entry(self, handle) -> None:
        raise NotImplementedError("must implement 'remove_entry'")

    def persist_entry(self, entry: DownloadEntry) -> None:
        raise NotImplementedError("must implement 'save_entry'")

    def flush(self) -> None:
        raise NotImplementedError("must implement 'flush'")

    @contextmanager
    def scoped_entry(self, handle: DownloadHandle) -> ContextManager[DownloadEntry]:
        try:
            entry = self.get_entry(handle)
            yield entry
            self.persist_entry(entry)
        except Exception as e:
            logger.warning(f"swallowed exception in scoped persistence block, not persisting {handle}: {e}")
            raise
