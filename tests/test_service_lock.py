import threading
import time

from pen_agent.config import Settings
from pen_agent.service import BusyError, PenService


def test_busy_lock(tmp_path, monkeypatch):
    settings = Settings(artifact_dir=tmp_path, profile="jingan")
    svc = PenService(settings)

    entered = threading.Event()
    release = threading.Event()

    def slow_status():
        with svc._exclusive():
            entered.set()
            release.wait(timeout=2)
            return {"ok": True}

    # Patch status path to hold the exclusive lock
    t = threading.Thread(target=slow_status)
    t.start()
    assert entered.wait(timeout=1)

    raised = False
    try:
        with svc._exclusive():
            pass
    except BusyError:
        raised = True
    assert raised
    release.set()
    t.join(timeout=2)
