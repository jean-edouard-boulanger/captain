from typing import Union

from .persistence import PersistenceBase
from .persistence_in_memory import InMemoryPersistence
from .persistence_sqlite import SQLitePersistence

PersistenceSettingsType = Union[
    SQLitePersistence.Settings, InMemoryPersistence.Settings
]


def get_persistence(settings: PersistenceSettingsType) -> PersistenceBase:
    if isinstance(settings, SQLitePersistence.Settings):
        return SQLitePersistence(settings)
    if isinstance(settings, InMemoryPersistence.Settings):
        return InMemoryPersistence(settings)
    raise KeyError(f"unsupported persistence type: {type(settings).__name__}")
