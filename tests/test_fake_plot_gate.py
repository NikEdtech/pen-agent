"""Live plot gate with a fake serial device (no hardware)."""

from pen_agent.config import Settings
from pen_agent.service import PenService
from tests.fake_grbl import FakeSerial


def test_live_plot_with_fake_serial(tmp_path, monkeypatch):
    from grbl_pen_plotter import grbl as grbl_mod

    ser = FakeSerial()

    def factory(*_a, **_k):
        return ser

    original_init = grbl_mod.Grbl.__init__

    def patched_init(self, port, baud=115200, **kw):
        kw["serial_factory"] = factory
        return original_init(self, port, baud, **kw)

    monkeypatch.setattr(grbl_mod.Grbl, "__init__", patched_init)

    settings = Settings(
        artifact_dir=tmp_path,
        profile="jingan",
        port="fake",
        dry_run_default=False,
        require_confirm_to_plot=True,
    )
    svc = PenService(settings)
    monkeypatch.setattr(svc, "resolve_port", lambda: "fake")

    denied = svc.write_text("OK", paper="A6", em_scale=0.3, dry_run=False, confirm=False)
    assert not denied.ok
    assert "confirm" in denied.message.lower()

    job = svc.write_text("OK", paper="A6", em_scale=0.3, dry_run=False, confirm=True)
    assert job.ok, job.message
    assert not job.dry_run
