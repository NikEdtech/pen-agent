"""Webcam capture via OpenCV (cross-platform)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple


def list_cameras(max_index: int = 6) -> List[int]:
    """Probe camera indices that open successfully."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python-headless is required for capture_photo") from exc

    found: List[int] = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        try:
            if cap is not None and cap.isOpened():
                ok, _ = cap.read()
                if ok:
                    found.append(i)
        finally:
            if cap is not None:
                cap.release()
    return found


def capture_photo(
    out_path: Path,
    *,
    camera_index: int = 0,
    warmup_frames: int = 5,
    size: Optional[Tuple[int, int]] = None,
) -> Path:
    """Capture a single frame to PNG/JPEG."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python-headless is required for capture_photo") from exc

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # CAP_DSHOW helps on Windows; ignored elsewhere
    backends = []
    if hasattr(cv2, "CAP_DSHOW"):
        backends.append(cv2.CAP_DSHOW)
    backends.append(cv2.CAP_ANY)

    last_err = "unknown"
    for backend in backends:
        cap = cv2.VideoCapture(camera_index, backend)
        try:
            if not cap.isOpened():
                last_err = f"cannot open camera {camera_index} backend={backend}"
                continue
            if size:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
            frame = None
            for _ in range(max(1, warmup_frames)):
                ok, frame = cap.read()
                if not ok:
                    last_err = "read failed"
            if frame is None:
                continue
            if not cv2.imwrite(str(out_path), frame):
                raise RuntimeError(f"failed to write {out_path}")
            return out_path
        finally:
            cap.release()
    raise RuntimeError(f"Webcam capture failed: {last_err}")
