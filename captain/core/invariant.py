from .logging import get_logger
from .errors import CaptainError

from typing import Any, Optional, Callable
from pathlib import Path
from dataclasses import dataclass
import os
import traceback
import signal
import inspect


logger = get_logger()


@dataclass
class ViolationMetadata:
    file_path: Path
    line_number: int
    broken_invariant: str
    stack_trace: str

    def describe(self) -> str:
        return (
            f"broken invariant: '{self.broken_invariant}'"
            f" in file: {self.file_path}"
            f" at line: {self.line_number}"
            f" backtrace:\n{self.stack_trace}"
        )


InvariantHandlerType = Callable[[ViolationMetadata], None]


def _abort_invariant_handler(metadata: ViolationMetadata) -> None:
    print("aborting")
    os.kill(os.getpid(), signal.SIGKILL)


def _exception_invariant_handler(metadata: ViolationMetadata) -> None:
    raise InvariantViolationError(metadata)


_INSTALLED_HANDLER: InvariantHandlerType = _exception_invariant_handler


class InvariantViolationError(CaptainError):
    def __init__(self, metadata: ViolationMetadata):
        super().__init__(metadata.describe())
        self._metadata = metadata

    @property
    def metadata(self) -> ViolationMetadata:
        return self._metadata


def _extract_broken_invariant_streamer(
    file_name: str, line_number: int
) -> Optional[str]:
    inv_call_symbol = "invariant("
    with open(file_name) as f:
        current_line_number = 0
        for line in f:
            current_line_number += 1
            if current_line_number < line_number:
                continue
            elif current_line_number == line_number:
                inv_index = line.find(inv_call_symbol)
                if inv_index == -1:
                    return
                rest = line[inv_index + len(inv_call_symbol) :]
                for current_char in rest.rstrip():
                    yield current_char
                yield " "
            else:
                for current_char in line.strip():
                    yield current_char
                yield " "


def _extract_broken_invariant_impl(file_name: str, line_number: int) -> Optional[str]:
    par_stack = ["("]
    output_buffer = str()
    for c in _extract_broken_invariant_streamer(file_name, line_number):
        if c == "(":
            par_stack.append(c)
        elif c == ")":
            if not par_stack:
                return None
            par_stack.pop()
            if len(par_stack) == 0:
                while output_buffer[0] == "(" and output_buffer[-1] == ")":
                    output_buffer = output_buffer[1:-1]
                return output_buffer.strip()
        output_buffer += c
    return None


def _extract_broken_invariant(file_name: str, line_number: int) -> Optional[str]:
    try:
        return _extract_broken_invariant_impl(file_name, line_number)
    except Exception as e:
        logger.warning(f"failed to extract broken invariant: {e}")
        return None


def _extract_broken_invariant_naive(raw_frame: str) -> str:
    for line in raw_frame.splitlines(keepends=False):
        if "invariant(" in line:
            return line.strip()
    return "unknown (please check source code from provided location)"


def invariant(check: bool):
    if check:
        return
    previous_frame = inspect.currentframe().f_back
    frame_info = inspect.getframeinfo(previous_frame)
    file_path = Path(frame_info.filename)
    line_number = frame_info.lineno
    broken_invariant = _extract_broken_invariant(file_path, line_number)
    broken_invariant = broken_invariant or _extract_broken_invariant_naive(
        traceback.format_stack()[-2]
    )
    metadata = ViolationMetadata(
        file_path=file_path,
        line_number=line_number,
        broken_invariant=broken_invariant,
        stack_trace="".join(traceback.format_stack()),
    )
    logger.error(metadata.describe())
    _INSTALLED_HANDLER(metadata)


def required_value(opt: Optional[Any]) -> Any:
    invariant(opt is not None)
    return opt
