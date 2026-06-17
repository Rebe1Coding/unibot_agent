import time
from threading import Lock

from prometheus_client import Counter, Gauge, Histogram

requests_total = Counter(
    "webgui_requests_total",
    "Total HTTP requests handled by web-gui",
    ["method", "endpoint", "status"],
)

request_latency = Histogram(
    "webgui_request_latency_seconds",
    "Web-gui request latency",
    ["method", "endpoint"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0),
)

active_users = Gauge(
    "webgui_active_users",
    "Unique user_id values seen in the last 5 minutes",
)


class ActiveUserTracker:
    def __init__(self, window_seconds: int):
        self._window = window_seconds
        self._seen: dict[str, float] = {}
        self._lock = Lock()

    def touch(self, user_id: str) -> None:
        if not user_id:
            return
        now = time.monotonic()
        with self._lock:
            self._seen[user_id] = now
            self._prune(now)
            active_users.set(len(self._seen))

    def refresh(self) -> int:
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            count = len(self._seen)
            active_users.set(count)
            return count

    def _prune(self, now: float) -> None:
        cutoff = now - self._window
        stale = [uid for uid, ts in self._seen.items() if ts < cutoff]
        for uid in stale:
            del self._seen[uid]
