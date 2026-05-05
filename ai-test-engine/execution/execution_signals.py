"""
Thread-safe stop signals for workflow execution.
Nodes check these between steps — the current step always completes.
"""
import threading

_lock = threading.Lock()
_stop_signals: set[str] = set()


def request_stop(run_id: str) -> None:
    with _lock:
        _stop_signals.add(run_id)


def is_stop_requested(run_id: str) -> bool:
    with _lock:
        return run_id in _stop_signals


def clear_stop(run_id: str) -> None:
    with _lock:
        _stop_signals.discard(run_id)
