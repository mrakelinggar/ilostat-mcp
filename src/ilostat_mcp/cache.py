"""
A small in-process cache with expiry, a size cap and a lock.

Used for ILOSTAT reference data (the dataflow catalogue, the country list)
and for fetched series. Memory only: nothing is written to disk, and
everything is lost when the process restarts.
"""

import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import Generic, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")

SECONDS_PER_HOUR = 60 * 60
SECONDS_PER_DAY = 24 * SECONDS_PER_HOUR


class TTLCache(Generic[K, V]):
    """
    Thread-safe cache whose entries expire after a time limit (TTL).

    When full, the least-recently-used entry is dropped (LRU), so memory is
    bounded by max_entries however much traffic arrives.

    Failures are never cached: if fetch() raises, nothing is stored and the
    next call tries again. Values must not be None (peek uses None for "absent").
    """

    def __init__(
        self,
        *,
        ttl_seconds: float,
        max_entries: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """
        Parameters
        ----------
        ttl_seconds : default lifetime of an entry
        max_entries : size cap; the least-recently-used entry is dropped first
        clock       : time source in seconds; injectable for tests
        """
        self._ttl = ttl_seconds
        self._max = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        # key -> (expires_at, value); order = least to most recently used
        self._entries: OrderedDict[K, tuple[float, V]] = OrderedDict()

    def peek(self, key: K) -> V | None:
        """Return the live value for key without fetching, or None."""
        with self._lock:
            return self._live(key)

    def get_or_fetch(
        self,
        key: K,
        fetch: Callable[[], V],
        ttl_for: Callable[[V], float] | None = None,
    ) -> V:
        """
        Return the cached value for key, calling fetch() on a miss or expiry.

        ttl_for, if given, picks the lifetime from the fetched value (e.g. a
        shorter one for "no data" results). fetch() runs outside the lock, so
        one slow request does not block lookups of other keys; two threads
        missing the same key at once may both fetch it, which is harmless.

        Raises whatever fetch() raises; nothing is cached in that case.
        """
        with self._lock:
            hit = self._live(key)
        if hit is not None:
            return hit

        value = fetch()
        ttl = ttl_for(value) if ttl_for is not None else self._ttl
        with self._lock:
            self._entries[key] = (self._clock() + ttl, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max:
                self._entries.popitem(last=False)
        return value

    def clear(self) -> None:
        """Drop every entry."""
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def _live(self, key: K) -> V | None:
        """Return key's value if present and unexpired; caller holds the lock."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if self._clock() >= expires_at:
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return value
