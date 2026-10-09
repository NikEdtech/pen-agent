"""Runtime configuration for pen-agent."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Settings:
    profile: str = "jingan"
    port: Optional[str] = None
    # Safety
    max_path_mm: float = 25000.0
    max_gcode_lines: int = 50000
    require_confirm_to_plot: bool = True
    # HTTP
    http_host: str = "0.0.0.0"
    http_port: int = 8765
    auth_token: str = ""
    # Camera
    camera_index: int = 0
    artifact_dir: Path = field(default_factory=lambda: Path("artifacts"))
    dry_run_default: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            profile=os.environ.get("PEN_AGENT_PROFILE", "jingan"),
            port=os.environ.get("PEN_AGENT_PORT") or None,
            max_path_mm=float(os.environ.get("PEN_AGENT_MAX_PATH_MM", "25000")),
            max_gcode_lines=int(os.environ.get("PEN_AGENT_MAX_LINES", "50000")),
            require_confirm_to_plot=os.environ.get("PEN_AGENT_REQUIRE_CONFIRM", "1")
            not in {"0", "false", "False"},
            http_host=os.environ.get("PEN_AGENT_HTTP_HOST", "0.0.0.0"),
            http_port=int(os.environ.get("PEN_AGENT_HTTP_PORT", "8765")),
            auth_token=os.environ.get("PEN_AGENT_TOKEN", ""),
            camera_index=int(os.environ.get("PEN_AGENT_CAMERA", "0")),
            artifact_dir=Path(os.environ.get("PEN_AGENT_ARTIFACT_DIR", "artifacts")),
            dry_run_default=os.environ.get("PEN_AGENT_DRY_RUN_DEFAULT", "1")
            not in {"0", "false", "False"},
        )
