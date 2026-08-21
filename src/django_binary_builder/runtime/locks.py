"""Initialization lock for the packaged application."""

import os
import time
from contextlib import contextmanager, suppress
from pathlib import Path

from django_binary_builder.exceptions import RuntimeInitializationError

DEFAULT_LOCK_TIMEOUT = 60.0
LOCK_RETRY_INTERVAL = 0.2
STALE_LOCK_SECONDS = 3600.0


@contextmanager
def initialization_lock(
    lock_path: Path,
    *,
    timeout: float = DEFAULT_LOCK_TIMEOUT,
):
    """Hold an exclusive initialization lock for the wrapped block."""

    lock_path.parent.mkdir(parents=True, exist_ok=True)

    handle = _acquire(lock_path, timeout=timeout)

    try:
        os.write(handle, str(os.getpid()).encode("ascii"))

        yield lock_path
    finally:
        os.close(handle)

        with suppress(FileNotFoundError):
            lock_path.unlink()


def _acquire(lock_path: Path, *, timeout: float) -> int:
    deadline = time.monotonic() + timeout

    while True:
        try:
            return os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError:
            _remove_stale_lock(lock_path)

            if time.monotonic() >= deadline:
                raise RuntimeInitializationError(
                    "Another application initialization is still in "
                    f"progress (lock: {lock_path})."
                ) from None

            time.sleep(LOCK_RETRY_INTERVAL)


def _remove_stale_lock(lock_path: Path) -> None:
    try:
        age = time.time() - lock_path.stat().st_mtime
    except OSError:
        return

    if age > STALE_LOCK_SECONDS:
        with suppress(OSError):
            lock_path.unlink()
