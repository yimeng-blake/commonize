"""Utility entrypoint for running the industry benchmark worker."""
from __future__ import annotations

import threading

from .industry_jobs import worker_loop


def main() -> None:  # pragma: no cover - thin wrapper
    stop = threading.Event()
    try:
        worker_loop(stop)
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":  # pragma: no cover
    main()
