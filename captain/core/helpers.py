import platform
from typing import Any


def make_kwargs(**kwargs: Any) -> dict[str, Any]:
    return kwargs


if platform.system() == "Linux":

    def set_thread_name(name: str):
        try:
            import pyprctl

            pyprctl.set_name(name)
        except Exception:
            pass

else:

    def set_thread_name(name: str):
        pass
