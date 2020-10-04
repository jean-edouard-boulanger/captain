from typing import Any, Optional
import os
import traceback
import signal


def _extract_invariant(raw_frame: str):
    for line in raw_frame.splitlines(keepends=False):
        if "invariant(" in line:
            return line.strip()


def _abort():
    os.kill(os.getpid(), signal.SIGKILL)


def check_invariants():
    if check_invariants.value is None:
        check_invariants.value = os.environ.get("CAPTAIN_SAFE_MODE", True)
    return check_invariants.value


check_invariants.value = None


def invariant(check: bool):
    if not check_invariants() or check:
        return
    stack = traceback.format_stack()
    calling_frame = traceback.format_stack()[-2]
    print(f"invariant broken near: {_extract_invariant(calling_frame)}")
    print("".join(stack))
    print("aborting")
    _abort()


def required_value(opt: Optional[Any]) -> Any:
    invariant(opt is not None)
    return opt
