from datetime import datetime, timedelta


class Throttle:
    def __init__(self, time_interval: timedelta):
        self._time_interval: timedelta = time_interval
        self._next_cutoff: datetime = self._next_cutoff_from_now()

    def _next_cutoff_from_now(self) -> datetime:
        return datetime.now() + self._time_interval

    def __call__(self, *args, **kwargs) -> bool:
        if self._next_cutoff is None or datetime.now() >= self._next_cutoff:
            self._next_cutoff = datetime.now() + self._time_interval
            return True
        return False
