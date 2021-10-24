import pytest

from captain.core.domain import (
    DownloadStatus,
    DownloadHandle,
    DownloadRequest,
    DownloadState,
    DownloadEntry,
)
from captain.core.persistence import (
    InMemoryPersistence,
    SQLitePersistence,
    PersistenceType,
    get_persistence,
)
from captain.core.serialization import pretty_dump


def create_dummy_download_entry() -> DownloadEntry:
    return DownloadEntry(
        handle=DownloadHandle.make(),
        user_request=DownloadRequest(remote_file_url=""),
        system_request=DownloadRequest(remote_file_url=""),
        state=DownloadState(status=DownloadStatus.ACTIVE),
    )


@pytest.mark.parametrize(
    "persistence_type,impl_type,kwargs",
    [
        (PersistenceType.IN_MEMORY, InMemoryPersistence, {}),
        (PersistenceType.SQLITE, SQLitePersistence, {"database_file_path": ":memory:"}),
    ],
)
def test_persistence(persistence_type, impl_type, kwargs):
    persistence = get_persistence(persistence_type, **kwargs)
    assert isinstance(persistence, impl_type)
    entry1 = create_dummy_download_entry()
    assert not persistence.has_entry(entry1.handle)
    persistence.persist_entry(entry1)
    assert persistence.has_entry(entry1.handle)
    persistence.persist_entry(entry1)
    entry1_back = persistence.get_entry(entry1.handle)
    assert pretty_dump(entry1) == pretty_dump(entry1_back)
    entry2 = create_dummy_download_entry()
    assert not persistence.has_entry(entry2.handle)
    persistence.persist_entry(entry2)
    assert persistence.has_entry(entry2.handle)
    entries = {entry.handle for entry in persistence.get_all_entries()}
    assert entry1.handle in entries
    assert entry2.handle in entries
