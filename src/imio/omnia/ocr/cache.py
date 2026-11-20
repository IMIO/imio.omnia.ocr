# -*- coding: utf-8 -*-
from collections import OrderedDict
from contextlib import contextmanager

import threading


class BoundedCache:
    """Small cache in the memory of the process.

    It keeps the most recently used entries.
    """

    def __init__(self, maxsize):
        self.maxsize = maxsize
        self._data = OrderedDict()
        self._key_locks = {}
        self._lock = threading.Lock()

    def get(self, key, default=None):
        with self._lock:
            if key not in self._data:
                return default
            self._data.move_to_end(key)
            return self._data[key]

    def set(self, key, value):
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)

    def discard(self, match):
        """Remove each entry for which ``match(key)`` is true."""
        with self._lock:
            for key in [key for key in self._data if match(key)]:
                del self._data[key]

    def clear(self):
        with self._lock:
            self._data.clear()

    @contextmanager
    def locked(self, key):
        """Let one thread at a time work on ``key``."""
        with self._lock:
            entry = self._key_locks.setdefault(key, [threading.Lock(), 0])
            entry[1] += 1
        try:
            with entry[0]:
                yield
        finally:
            with self._lock:
                entry[1] -= 1
                if not entry[1]:
                    self._key_locks.pop(key, None)
