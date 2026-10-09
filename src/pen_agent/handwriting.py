"""Handwriting-looking strokes: jitter, baseline wobble, postcard templates."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

from grbl_pen_plotter.profile import PAPER, PaperSize
from grbl_pen_plotter.text import text_to_strokes

Point = Tuple[float, float]
Stroke = List[Point]

PAPER_ALIASES = {
    "a4": "A4",
    "a5": "A5",
    "a6": "A6",
    "postcard": "postcard",
    "thankyou": "postcard",
    "thank-you": "postcard",
}


@dataclass
class Layout:
    paper: str = "A5"
    margin_mm: float = 12.0
    em_scale: float = 0.42
    line_spacing: float = 1.25
    jitter_mm: float = 0.08
    baseline_wobble_mm: float = 0.15
    seed: int = 1
    recipient: str = ""
    sign_off: str = ""
    brand: str = ""


def resolve_paper(name: str) -> PaperSize:
    key = PAPER_ALIASES.get(name.lower(), name.upper())
    if key == "postcard":
        return PaperSize("postcard", 148.0, 105.0)  # A6 landscape-ish greeting
    if key in PAPER:
        return PAPER[key]
    raise ValueError(f"Unknown paper: {name} (try A4/A5/A6/postcard)")


def apply_handwriting(
    strokes: List[Stroke],
    *,
    jitter_mm: float,
    baseline_wobble_mm: float,
    seed: int,
) -> List[Stroke]:
    """Add natural single-stroke variation without breaking connectivity much."""
    if jitter_mm <= 0 and baseline_wobble_mm <= 0:
        return strokes
    rng = random.Random(seed)
    out: List[Stroke] = []
    for si, stroke in enumerate(strokes):
        # per-stroke baseline drift
        base = rng.uniform(-baseline_wobble_mm, baseline_wobble_mm)
        ns: Stroke = []
        for i, (x, y) in enumerate(stroke):
            jx = rng.uniform(-jitter_mm, jitter_mm) if jitter_mm else 0.0
            jy = rng.uniform(-jitter_mm, jitter_mm) if jitter_mm else 0.0
            # slight progressive drift along stroke
            drift = base + (i / max(len(stroke) - 1, 1)) * rng.uniform(
                -baseline_wobble_mm * 0.3, baseline_wobble_mm * 0.3
            )
            ns.append((x + jx, y + jy + drift))
        if len(ns) >= 2:
            out.append(ns)
    return out


def layout_text(
    text: str,
    layout: Layout,
) -> List[Stroke]:
    paper = resolve_paper(layout.paper)
    max_width = paper.width_mm - 2 * layout.margin_mm
    blocks: List[str] = []
    if layout.recipient:
        blocks.append(f"{layout.recipient},")
    blocks.append(text.strip())
    if layout.sign_off or layout.brand:
        tail = layout.sign_off or ""
        if layout.brand:
            tail = f"{tail}\n{layout.brand}".strip()
        blocks.append(tail)

    y = layout.margin_mm
    all_strokes: List[Stroke] = []
    for bi, block in enumerate(blocks):
        scale = layout.em_scale * (1.05 if bi == 0 and layout.recipient else 1.0)
        if bi == len(blocks) - 1 and (layout.sign_off or layout.brand):
            scale = layout.em_scale * 0.9
        strokes = text_to_strokes(
            block,
            origin=(layout.margin_mm, y),
            scale=scale,
            line_spacing=layout.line_spacing,
            max_width=max_width,
        )
        all_strokes.extend(strokes)
        # advance y roughly by line count
        lines = max(block.count("\n") + 1, 1)
        y += lines * 18.0 * scale * layout.line_spacing + 4.0

    return apply_handwriting(
        all_strokes,
        jitter_mm=layout.jitter_mm,
        baseline_wobble_mm=layout.baseline_wobble_mm,
        seed=layout.seed,
    )


def thank_you_card(
    name: str,
    message: Optional[str] = None,
    *,
    brand: str = "Thank you",
    layout: Optional[Layout] = None,
) -> List[Stroke]:
    """Small-shop thank-you postcard template."""
    lay = layout or Layout(paper="postcard", em_scale=0.4, jitter_mm=0.1, baseline_wobble_mm=0.18)
    lay.recipient = name
    lay.brand = brand
    lay.sign_off = lay.sign_off or "—"
    body = message or (
        f"спасибо, что выбрали нас.\n"
        f"Thank you for your order — it means a lot."
    )
    return layout_text(body, lay)
