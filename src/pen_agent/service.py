"""Plotter service: job lock, bounds, dry-run default, GRBL ops."""

from __future__ import annotations

import base64
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from grbl_pen_plotter.bounds import check_gcode_file, check_strokes
from grbl_pen_plotter.gcode import emit_strokes
from grbl_pen_plotter.grbl import AlarmError, Grbl, GrblError, make_logger
from grbl_pen_plotter.ports import autodetect_port, list_ports
from grbl_pen_plotter.preview import gcode_to_strokes, render_preview
from grbl_pen_plotter.profile import Profile, resolve_profile
from grbl_pen_plotter.stream import stream_file
from grbl_pen_plotter.svg import extract_strokes, fit_strokes

from pen_agent.camera import capture_photo, list_cameras
from pen_agent.config import Settings
from pen_agent.handwriting import Layout, layout_text, resolve_paper, thank_you_card

Point = Tuple[float, float]
Stroke = List[Point]


@dataclass
class JobResult:
    ok: bool
    dry_run: bool
    job_id: str
    message: str
    gcode_path: Optional[str] = None
    preview_path: Optional[str] = None
    preview_png_b64: Optional[str] = None
    path_mm: float = 0.0
    lines: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)


class BusyError(RuntimeError):
    pass


class PenService:
    """Thread-safe façade used by the MCP server."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings.from_env()
        self.settings.artifact_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._busy = False
        self._grbl: Optional[Grbl] = None
        self._profile: Optional[Profile] = None
        self._last_abort: Optional[Grbl] = None

    # --- ports / status -------------------------------------------------

    def list_ports(self) -> List[Dict[str, str]]:
        ports = list_ports()
        auto = autodetect_port(self._profile_hint())
        for p in ports:
            p["autodetect"] = str(p["device"] == auto)
        return ports

    def _profile_hint(self) -> str:
        try:
            return resolve_profile(self.settings.profile).default_port_hint
        except Exception:
            return "CH340"

    def resolve_port(self) -> Optional[str]:
        return self.settings.port or autodetect_port(self._profile_hint())

    def status(self) -> Dict[str, Any]:
        port = self.resolve_port()
        if not port:
            return {"connected": False, "message": "No plotter port found", "ports": self.list_ports()}
        with self._exclusive():
            g = self._connect(port)
            try:
                st = g.status()
                if not st:
                    return {"connected": True, "port": port, "message": "No status response"}
                return {
                    "connected": True,
                    "port": port,
                    "state": st.state,
                    "x": st.x,
                    "y": st.y,
                    "z": st.z,
                    "wpos": st.wpos,
                    "raw": st.raw,
                    "busy": self._busy,
                }
            finally:
                self._disconnect()

    # --- pen helpers ----------------------------------------------------

    def pen_up(self) -> Dict[str, Any]:
        with self._exclusive():
            g, profile = self._ensure()
            g.pen_up(profile)
            st = g.status()
            return {"ok": True, "action": "up", "z": st.z if st else None}

    def pen_down(self) -> Dict[str, Any]:
        with self._exclusive():
            g, profile = self._ensure()
            g.ensure_plotting_hold(profile)
            g.pen_down(profile)
            st = g.status()
            return {"ok": True, "action": "down", "z": st.z if st else None}

    def home(self) -> Dict[str, Any]:
        """Set work zero at current raised pose (not GRBL $H)."""
        with self._exclusive():
            g, profile = self._ensure()
            g.pen_up(profile)
            g.set_work_zero()
            st = g.status()
            return {
                "ok": True,
                "action": "home_work_zero",
                "message": "G92 X0 Y0 Z0 at current pose — keep pen raised",
                "status": st.raw if st else None,
            }

    def abort(self) -> Dict[str, Any]:
        with self._lock:
            g = self._grbl or self._last_abort
            profile = self._profile or resolve_profile(self.settings.profile)
            if g is None:
                port = self.resolve_port()
                if not port:
                    return {"ok": False, "message": "Nothing to abort (no connection)"}
                g = Grbl(port, profile.grbl.baud, log=make_logger())
                g.connect(soft_reset=False)
            try:
                g.abort_safe(profile)
                return {"ok": True, "message": "Aborted: soft-reset + pen up"}
            except Exception as exc:
                return {"ok": False, "message": str(exc)}
            finally:
                self._busy = False

    # --- content --------------------------------------------------------

    def write_text(
        self,
        text: str,
        *,
        paper: str = "A5",
        em_scale: float = 0.42,
        jitter_mm: float = 0.08,
        baseline_wobble_mm: float = 0.15,
        recipient: str = "",
        sign_off: str = "",
        brand: str = "",
        template: str = "",
        seed: int = 1,
        dry_run: Optional[bool] = None,
        confirm: bool = False,
    ) -> JobResult:
        if template in {"thankyou", "thank-you", "postcard"}:
            strokes = thank_you_card(
                recipient or "friend",
                text,
                brand=brand or "Thank you",
                layout=Layout(
                    paper="postcard",
                    em_scale=em_scale,
                    jitter_mm=jitter_mm,
                    baseline_wobble_mm=baseline_wobble_mm,
                    seed=seed,
                    sign_off=sign_off,
                ),
            )
            paper = "postcard"
        else:
            strokes = layout_text(
                text,
                Layout(
                    paper=paper,
                    em_scale=em_scale,
                    jitter_mm=jitter_mm,
                    baseline_wobble_mm=baseline_wobble_mm,
                    seed=seed,
                    recipient=recipient,
                    sign_off=sign_off,
                    brand=brand,
                ),
            )
        return self._job_from_strokes(strokes, source=f"text:{template or paper}", dry_run=dry_run, confirm=confirm)

    def draw_svg(
        self,
        svg: str,
        *,
        paper: str = "A5",
        margin_mm: float = 10.0,
        dry_run: Optional[bool] = None,
        confirm: bool = False,
    ) -> JobResult:
        # svg may be path or raw XML
        path = Path(svg)
        if path.is_file():
            strokes = extract_strokes(path)
            src = str(path)
        else:
            strokes = extract_strokes(svg)
            src = "svg:inline"
        if not strokes:
            return JobResult(False, True, "", "No strokes found in SVG")
        paper_size = resolve_paper(paper)
        fitted, scale = fit_strokes(
            strokes,
            paper=paper_size if paper_size.name != "postcard" else "A6",
            margin_mm=margin_mm,
            target_width=paper_size.width_mm,
            target_height=paper_size.height_mm,
        )
        return self._job_from_strokes(
            fitted,
            source=f"{src}|scale={scale:.4f}",
            dry_run=dry_run,
            confirm=confirm,
        )

    def preview_gcode(self, gcode: str) -> Dict[str, Any]:
        job_id = uuid.uuid4().hex[:10]
        out = self.settings.artifact_dir / f"preview_{job_id}.png"
        strokes = gcode_to_strokes(gcode)
        render_preview(strokes, out)
        b64 = base64.b64encode(out.read_bytes()).decode("ascii")
        return {
            "ok": True,
            "preview_path": str(out),
            "preview_png_b64": b64,
            "strokes": len(strokes),
        }

    def plot_gcode(
        self,
        gcode: str,
        *,
        dry_run: Optional[bool] = None,
        confirm: bool = False,
        set_zero: bool = False,
        cool: bool = True,
    ) -> JobResult:
        dry = self.settings.dry_run_default if dry_run is None else dry_run
        job_id = uuid.uuid4().hex[:10]
        profile = resolve_profile(self.settings.profile)
        report = check_gcode_file(gcode, profile.limits)
        if not report.ok:
            return JobResult(
                False,
                dry,
                job_id,
                f"Bounds check failed: {report.message}",
                extra={"out_sample": report.out_sample},
            )
        if report.path_length_mm > self.settings.max_path_mm:
            return JobResult(
                False,
                dry,
                job_id,
                f"Path too long: {report.path_length_mm:.0f} mm > {self.settings.max_path_mm}",
            )
        lines = [ln for ln in gcode.splitlines() if ln.split(";")[0].strip()]
        if len(lines) > self.settings.max_gcode_lines:
            return JobResult(False, dry, job_id, f"Too many lines: {len(lines)}")

        gcode_path = self.settings.artifact_dir / f"job_{job_id}.gcode"
        gcode_path.write_text(gcode, encoding="utf-8")
        preview_path = self.settings.artifact_dir / f"job_{job_id}.png"
        render_preview(gcode_to_strokes(gcode), preview_path)
        b64 = base64.b64encode(preview_path.read_bytes()).decode("ascii")

        if dry:
            return JobResult(
                True,
                True,
                job_id,
                "Dry-run OK — pass dry_run=false and confirm=true to plot on hardware",
                gcode_path=str(gcode_path),
                preview_path=str(preview_path),
                preview_png_b64=b64,
                path_mm=report.path_length_mm,
                lines=len(lines),
            )

        if self.settings.require_confirm_to_plot and not confirm:
            return JobResult(
                False,
                False,
                job_id,
                "Refusing live plot without confirm=true (safety)",
                gcode_path=str(gcode_path),
                preview_path=str(preview_path),
                preview_png_b64=b64,
                path_mm=report.path_length_mm,
                lines=len(lines),
            )

        with self._exclusive():
            g, profile = self._ensure()
            g.ensure_plotting_hold(profile)
            if set_zero:
                g.pen_up(profile)
                g.set_work_zero()
            try:
                result = stream_file(g, gcode, profile=profile)
            except AlarmError as exc:
                g.abort_safe(profile)
                return JobResult(False, False, job_id, f"ALARM: {exc}", gcode_path=str(gcode_path))
            except GrblError as exc:
                g.abort_safe(profile)
                return JobResult(False, False, job_id, f"GRBL error: {exc}", gcode_path=str(gcode_path))

            if cool and result.ok:
                try:
                    g.cool_motors(profile)
                except Exception:
                    pass
            return JobResult(
                result.ok,
                False,
                job_id,
                "Plot complete" if result.ok else (result.error or "failed"),
                gcode_path=str(gcode_path),
                preview_path=str(preview_path),
                preview_png_b64=b64,
                path_mm=report.path_length_mm,
                lines=result.lines_sent,
            )

    def capture_photo(self, camera_index: Optional[int] = None) -> Dict[str, Any]:
        idx = self.settings.camera_index if camera_index is None else camera_index
        out = self.settings.artifact_dir / f"photo_{int(time.time())}.jpg"
        path = capture_photo(out, camera_index=idx)
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return {
            "ok": True,
            "path": str(path),
            "camera_index": idx,
            "available": list_cameras(),
            "image_jpeg_b64": b64,
        }

    # --- internals ------------------------------------------------------

    def _job_from_strokes(
        self,
        strokes: List[Stroke],
        *,
        source: str,
        dry_run: Optional[bool],
        confirm: bool,
    ) -> JobResult:
        profile = resolve_profile(self.settings.profile)
        # Temporarily widen work limits to paper if strokes are small
        report = check_strokes(strokes, profile.limits)
        try:
            gcode, report = emit_strokes(strokes, profile, source=source, validate=True)
        except ValueError as exc:
            return JobResult(False, True, "", str(exc))
        return self.plot_gcode(gcode, dry_run=dry_run, confirm=confirm)

    def _connect(self, port: str) -> Grbl:
        profile = resolve_profile(self.settings.profile)
        g = Grbl(port, profile.grbl.baud, log=make_logger())
        g.connect(soft_reset=profile.grbl.soft_reset_on_connect)
        g.unlock()
        self._grbl = g
        self._profile = profile
        self._last_abort = g
        return g

    def _disconnect(self) -> None:
        if self._grbl is not None:
            try:
                self._grbl.close()
            except Exception:
                pass
            self._grbl = None

    def _ensure(self) -> Tuple[Grbl, Profile]:
        port = self.resolve_port()
        if not port:
            raise GrblError("No plotter port — set PEN_AGENT_PORT or plug in USB-serial")
        if self._grbl is None:
            self._connect(port)
        assert self._grbl and self._profile
        return self._grbl, self._profile

    def _exclusive(self):
        service = self

        class _Ctx:
            def __enter__(self_nonlocal):
                if not service._lock.acquire(blocking=False):
                    raise BusyError("Another pen-agent job is running")
                if service._busy:
                    service._lock.release()
                    raise BusyError("Another pen-agent job is running")
                service._busy = True
                return service

            def __exit__(self_nonlocal, *exc):
                service._busy = False
                try:
                    service._disconnect()
                finally:
                    service._lock.release()

        return _Ctx()
