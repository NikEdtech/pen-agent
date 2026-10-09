"""pen-agent CLI helpers (non-MCP)."""

from __future__ import annotations

import argparse
import json
import sys

from pen_agent import __version__
from pen_agent.config import Settings
from pen_agent.service import PenService


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="pen-agent", description="Give your agent a pen")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ports", help="List serial ports")
    sub.add_parser("status", help="Plotter status")
    sp = sub.add_parser("thankyou", help="Dry-run thank-you postcard")
    sp.add_argument("name")
    sp.add_argument("--message", default="")
    sp.add_argument("--brand", default="Thank you")

    sp = sub.add_parser("photo", help="Capture webcam snapshot")
    sp.add_argument("--camera", type=int, default=-1)

    sp = sub.add_parser("serve", help="Run MCP server")
    sp.add_argument("--transport", default="stdio", choices=["stdio", "http", "streamable-http"])
    sp.add_argument("--host", default=None)
    sp.add_argument("--port", type=int, default=None)

    args = p.parse_args(argv)
    settings = Settings.from_env()
    svc = PenService(settings)

    if args.cmd == "ports":
        print(json.dumps(svc.list_ports(), indent=2))
        return 0
    if args.cmd == "status":
        print(json.dumps(svc.status(), indent=2))
        return 0
    if args.cmd == "thankyou":
        job = svc.write_text(
            args.message or "спасибо за заказ!",
            template="thankyou",
            recipient=args.name,
            brand=args.brand,
            dry_run=True,
        )
        print(json.dumps({
            "ok": job.ok,
            "message": job.message,
            "preview_path": job.preview_path,
            "gcode_path": job.gcode_path,
            "path_mm": job.path_mm,
        }, indent=2))
        return 0 if job.ok else 1
    if args.cmd == "photo":
        idx = None if args.camera < 0 else args.camera
        try:
            print(json.dumps({k: v for k, v in svc.capture_photo(idx).items() if k != "image_jpeg_b64"}, indent=2))
            return 0
        except Exception as exc:
            print(json.dumps({"ok": False, "message": str(exc)}), file=sys.stderr)
            return 1
    if args.cmd == "serve":
        from pen_agent.server import main as server_main

        argv2 = ["--transport", args.transport]
        if args.host:
            argv2 += ["--host", args.host]
        if args.port:
            argv2 += ["--port", str(args.port)]
        server_main(argv2)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
