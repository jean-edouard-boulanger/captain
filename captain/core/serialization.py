from typing import Any, Optional, Union
from pathlib import PurePath
from datetime import datetime, date, timedelta
import decimal
import json

import pydantic


def serialize(data: Any) -> Any:
    def serialize_key(key: Any) -> Optional[Union[str, int, float, bool]]:
        if key is None:
            return key
        if not isinstance(key, (str, int, float, bool)):
            return str(key)
        return key

    if hasattr(data, "serialize"):
        return serialize(data.serialize())
    if isinstance(data, pydantic.BaseModel):
        return serialize(data.dict())
    if isinstance(data, decimal.Decimal):
        return float(data)
    if isinstance(data, (datetime, date)):
        return data.isoformat()
    if isinstance(data, timedelta):
        return data.total_seconds()
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
