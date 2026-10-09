"""MCP server (stdio + streamable HTTP) for pen-agent."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Optional

from pen_agent import __version__
from pen_agent.config import Settings
from pen_agent.service import BusyError, JobResult, PenService

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "The 'mcp' package is required (Python >= 3.10). "
        "Install with: pip install 'pen-agent'"
    ) from exc


def _job_dict(job: JobResult) -> Dict[str, Any]:
    return {
        "ok": job.ok,
        "dry_run": job.dry_run,
        "job_id": job.job_id,
        "message": job.message,
        "gcode_path": job.gcode_path,
        "preview_path": job.preview_path,
        "preview_png_b64": job.preview_png_b64,
        "path_mm": job.path_mm,
        "lines": job.lines,
        "extra": job.extra,
    }


def build_mcp(settings: Optional[Settings] = None) -> FastMCP:
    settings = settings or Settings.from_env()
    service = PenService(settings)
    mcp = FastMCP(
        "pen-agent",
        instructions=(
            "Give your agent a pen. Control a GRBL pen plotter: write handwriting "
            "(Latin+Cyrillic), draw SVG, preview toolpaths, capture a webcam photo. "
            "plot() defaults to dry-run; set dry_run=false AND confirm=true for hardware. "
            "Always preview and confirm with the human before a live plot."
        ),
    )

    @mcp.tool()
    def list_ports() -> str:
        """List serial ports; autodetect candidate is marked."""
        return json.dumps(service.list_ports(), indent=2)

    @mcp.tool()
    def status() -> str:
        """Query GRBL status (Idle/Run, position) or report disconnected."""
        return json.dumps(service.status(), indent=2)

    @mcp.tool()
    def write_text(
        text: str,
        paper: str = "A5",
        em_scale: float = 0.42,
        jitter_mm: float = 0.08,
        baseline_wobble_mm: float = 0.15,
        recipient: str = "",
        sign_off: str = "",
        brand: str = "",
        template: str = "",
        seed: int = 1,
        dry_run: bool = True,
        confirm: bool = False,
    ) -> str:
        """Render handwriting text to G-code and optionally plot.

        template='thankyou' builds a postcard thank-you note.
        Defaults to dry_run=True. Live plot requires dry_run=false and confirm=true.
        """
        try:
            job = service.write_text(
                text,
                paper=paper,
                em_scale=em_scale,
                jitter_mm=jitter_mm,
                baseline_wobble_mm=baseline_wobble_mm,
                recipient=recipient,
                sign_off=sign_off,
                brand=brand,
                template=template,
                seed=seed,
                dry_run=dry_run,
                confirm=confirm,
            )
        except BusyError as exc:
            return json.dumps({"ok": False, "message": str(exc)})
        return json.dumps(_job_dict(job))

    @mcp.tool()
    def draw_svg(
        svg: str,
        paper: str = "A5",
        margin_mm: float = 10.0,
        dry_run: bool = True,
        confirm: bool = False,
    ) -> str:
        """Convert SVG path/file to G-code and optionally plot (dry-run by default)."""
        try:
            job = service.draw_svg(
                svg, paper=paper, margin_mm=margin_mm, dry_run=dry_run, confirm=confirm
            )
        except BusyError as exc:
            return json.dumps({"ok": False, "message": str(exc)})
        return json.dumps(_job_dict(job))

    @mcp.tool()
    def preview(gcode: str = "", preview_path: str = "") -> str:
        """Render a toolpath preview PNG (from G-code text or an existing .gcode path)."""
        if preview_path:
            text = open(preview_path, encoding="utf-8").read()
        else:
            text = gcode
        if not text.strip():
            return json.dumps({"ok": False, "message": "Provide gcode or preview_path"})
        return json.dumps(service.preview_gcode(text))

    @mcp.tool()
    def plot(
        gcode: str = "",
        gcode_path: str = "",
        dry_run: bool = True,
        confirm: bool = False,
        set_zero: bool = False,
        cool: bool = True,
    ) -> str:
        """Stream G-code. Defaults to dry-run. Live plot needs dry_run=false and confirm=true."""
        text = gcode
        if gcode_path:
            text = open(gcode_path, encoding="utf-8").read()
        if not text.strip():
            return json.dumps({"ok": False, "message": "Provide gcode or gcode_path"})
        try:
            job = service.plot_gcode(
                text, dry_run=dry_run, confirm=confirm, set_zero=set_zero, cool=cool
            )
        except BusyError as exc:
            return json.dumps({"ok": False, "message": str(exc)})
        return json.dumps(_job_dict(job))

    @mcp.tool()
    def pen_up() -> str:
        """Raise the pen (Z up + M5)."""
        try:
            return json.dumps(service.pen_up())
        except Exception as exc:
            return json.dumps({"ok": False, "message": str(exc)})

    @mcp.tool()
    def pen_down() -> str:
        """Lower the pen (M3 + Z down)."""
        try:
            return json.dumps(service.pen_down())
        except Exception as exc:
            return json.dumps({"ok": False, "message": str(exc)})

    @mcp.tool()
    def home() -> str:
        """Set work zero (G92) at current raised pose. Not machine homing $H."""
        try:
            return json.dumps(service.home())
        except Exception as exc:
            return json.dumps({"ok": False, "message": str(exc)})

    @mcp.tool()
    def abort() -> str:
        """Emergency stop: soft-reset and raise pen."""
        return json.dumps(service.abort())

    @mcp.tool()
    def capture_photo(camera_index: int = -1) -> str:
        """Capture a webcam frame so the agent can see the paper/result."""
        try:
            idx = None if camera_index < 0 else camera_index
            return json.dumps(service.capture_photo(idx))
        except Exception as exc:
            return json.dumps({"ok": False, "message": str(exc)})

    return mcp


def main(argv: Optional[list] = None) -> None:
    parser = argparse.ArgumentParser(description=f"pen-agent MCP server v{__version__}")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "streamable-http", "sse"],
        default=os.environ.get("PEN_AGENT_TRANSPORT", "stdio"),
    )
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    if args.host:
        settings.http_host = args.host
    if args.port:
        settings.http_port = args.port

    mcp = build_mcp(settings)
    transport = args.transport
    if transport == "http":
        transport = "streamable-http"

    if transport == "stdio":
        mcp.run(transport="stdio")
        return

    # HTTP / SSE — optional bearer token via middleware when supported
    token = settings.auth_token
    if token:
        os.environ.setdefault("PEN_AGENT_TOKEN", token)
        print(
            f"pen-agent HTTP on {settings.http_host}:{settings.http_port} "
            f"(auth token required via PEN_AGENT_TOKEN / Authorization: Bearer)",
            flush=True,
        )
    else:
        print(
            f"WARNING: PEN_AGENT_TOKEN unset — HTTP endpoint is open on "
            f"{settings.http_host}:{settings.http_port}",
            flush=True,
        )

    # FastMCP run signatures vary slightly across versions; try kwargs then fallback.
    try:
        mcp.run(
            transport=transport,
            host=settings.http_host,
            port=settings.http_port,
        )
    except TypeError:
        # Older FastMCP: set settings then run
        try:
            mcp.settings.host = settings.http_host
            mcp.settings.port = settings.http_port
        except Exception:
            pass
        mcp.run(transport=transport)


if __name__ == "__main__":
    main()
