"""The captcha browser is built outside any pool here, so the construction
scope is a plain lock (one browser starts at a time)."""
import threading
from contextlib import contextmanager

_create_lock = threading.Lock()


@contextmanager
def create_scope():
    with _create_lock:
        yield
