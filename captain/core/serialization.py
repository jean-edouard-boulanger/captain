import json
import uuid
from datetime import date, datetime, timedelta
from pathlib import PurePath
from typing import Any

import orjson
import pydantic


def serialize(data: Any) -> Any:
    def serialize_key(key: Any) -> str | int | float | bool | None:
        if key is None:
            return key
        if not isinstance(key, (str, int, float, bool)):
            return str(key)
        return key

    if isinstance(data, pydantic.BaseModel):
        return serialize(data.dict())
    if isinstance(data, (datetime, date)):
        return data.isoformat()
    if isinstance(data, timedelta):
        return data.total_seconds()
    if isinstance(data, uuid.UUID):
        return str(data)
    if isinstance(data, dict):
        return {serialize_key(k): serialize(v) for k, v in data.items()}
    if isinstance(data, (list, set, tuple)):
        return [serialize(v) for v in data]
    if issubclass(type(data), PurePath):
        return str(data)
    return data


def serializer(func):
    def impl(*args, **kwargs):
        return serialize(func(*args, **kwargs))

    return impl


def pretty_dump(data: Any) -> str:
    return json.dumps(serialize(data), indent=4, sort_keys=True)


def to_json(data: Any) -> str:
    return orjson.dumps(data).decode()
