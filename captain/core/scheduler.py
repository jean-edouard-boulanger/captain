from .logging import get_logger
from .future import Future

from typing import Callable, Dict, Optional, Union
from dataclasses import dataclass
from queue import Queue
from threading import Thread
from datetime import datetime
import queue
import pytz


logger = get_logger()


def _now_utc() -> datetime:
    return datetime.now(pytz.utc)


def _pop_queue(q: Queue, timeout: float):
    try:
        return q.get(block=True, timeout=timeout)
    except queue.Empty:
        return None


Action = Callable[[], None]


@dataclass
class _Entry:
    at: datetime
    action: Action


@dataclass
class _StopScheduler:
    pass


@dataclass
class _Schedule:
    entry: _Entry


@dataclass
class _Cancel:
    handle: int


_EventType = Union[_StopScheduler, _Schedule, _Cancel]


@dataclass
class _Event:
    payload: _EventType
    future: Future


class Scheduler(object):
    def __init__(self):
        self._events = Queue()
        self._pending_actions: Dict[int, _Entry] = {}
        self._running = True
        self._last_handle = 0

    def run(self):
        logger.info("scheduler started")
        while True:
            timeout = self._time_to_next_action()
            event = _pop_queue(self._events, timeout)
            if event is not None:
                logger.debug(f"handling event: {event}")
                self._handle_event(event)
            if not self._running:
                logger.info("scheduler no longer running")
                logger.info(
                    f"leaving main loop with {len(self._pending_actions)} pending actions"
                )
                return
            now = _now_utc()
            cleanup_handles = []
            for handle, entry in self._pending_actions.items():
                if entry.at <= now:
                    logger.debug(
                        f"pending action [{handle}] {entry} if overdue to run, running now"
                    )
                    entry.action()
                    cleanup_handles.append(handle)
            for handle in cleanup_handles:
                logger.debug(f"cleaning up handle {handle}")
                del self._pending_actions[handle]

    def schedule(self, at: datetime, action: Action):
        logger.debug(
            f"requested to schedule action {action} at {at} "
            f"(in {(at - _now_utc()).total_seconds()}s)"
        )
        return self._queue_event(_Schedule(_Entry(at, action))).get()

    def schedule_unsafe(self, at: datetime, action: Action):
        handle = self._allocate_handle()
        self._pending_actions[handle] = _Entry(at, action)
        return handle

    def cancel(self, handle: int):
        logger.debug(f"requested to cancel scheduled action {handle}")
        return self._queue_event(_Cancel(handle)).get()

    def stop(self):
        logger.debug("scheduler requested to stop")
        return self._queue_event(_StopScheduler()).get()

    def _time_to_next_action(self) -> Optional[float]:
        if len(self._pending_actions) == 0:
            return None
        now = _now_utc()
        min_interval = min(
            (entry.at - now).total_seconds() for entry in self._pending_actions.values()
        )
        return max(min_interval, 0)

    def _handle_event_impl(self, event: _Event):
        payload = event.payload
        if isinstance(payload, _StopScheduler):
            self._running = False
            event.future.set_result(None)
        elif isinstance(payload, _Schedule):
            entry = event.payload.entry
            event.future.set_result(self.schedule_unsafe(entry.at, entry.action))
        elif isinstance(payload, _Cancel):
            del self._pending_actions[payload.handle]
            event.future.set_result(None)

    def _handle_event(self, event: _Event):
        try:
            self._handle_event_impl(event)
        except Exception as e:
            event.future.set_error(e)

    def _allocate_handle(self) -> int:
        handle = self._last_handle
        self._last_handle += 1
        return handle

    def _queue_event(self, payload: _EventType) -> Future:
        future = Future()
        self._events.put(_Event(payload, future))
        return future


class ThreadedScheduler(Thread):
    def __init__(self, scheduler: Scheduler):
        super().__init__()
        self._scheduler = scheduler

    def run(self) -> None:
        return self._scheduler.run()

    def schedule(self, at: datetime, action: Action):
        return self._scheduler.schedule(at, action)

    def schedule_unsafe(self, at: datetime, action: Action):
        return self._scheduler.schedule_unsafe(at, action)

    def cancel(self, handle: int):
        return self._scheduler.cancel(handle)

    def stop(self):
        return self._scheduler.stop()
