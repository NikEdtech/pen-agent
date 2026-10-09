from pathlib import Path

from pen_agent.config import Settings
from pen_agent.handwriting import layout_text, Layout, thank_you_card
from pen_agent.service import PenService


def test_layout_cyrillic_jitter(tmp_path: Path):
    strokes = layout_text(
        "Привет Test",
        Layout(paper="A6", em_scale=0.35, jitter_mm=0.1, baseline_wobble_mm=0.12, seed=7),
    )
    assert len(strokes) >= 5
    # jitter should change coordinates vs zero-jitter
    clean = layout_text(
        "Привет Test",
        Layout(paper="A6", em_scale=0.35, jitter_mm=0.0, baseline_wobble_mm=0.0, seed=7),
    )
    assert strokes[0][0] != clean[0][0] or strokes[0][1] != clean[0][1]


def test_thankyou_dry_run(tmp_path: Path):
    settings = Settings(artifact_dir=tmp_path, dry_run_default=True, profile="jingan")
    svc = PenService(settings)
    job = svc.write_text(
        "спасибо за заказ!",
        template="thankyou",
        recipient="Анна",
        brand="Demo Shop",
        dry_run=True,
    )
    assert job.ok
    assert job.dry_run
    assert job.preview_path and Path(job.preview_path).is_file()
    assert job.gcode_path and Path(job.gcode_path).is_file()
    assert "G1" in Path(job.gcode_path).read_text()


def test_plot_requires_confirm(tmp_path: Path):
    settings = Settings(
        artifact_dir=tmp_path,
        dry_run_default=False,
        require_confirm_to_plot=True,
        profile="jingan",
    )
    svc = PenService(settings)
    job = svc.write_text("Hi", paper="A6", em_scale=0.3, dry_run=False, confirm=False)
    assert not job.ok
    assert "confirm" in job.message.lower()


def test_svg_dry_run(tmp_path: Path):
    svg = tmp_path / "x.svg"
    svg.write_text(
        """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">
  <rect x="2" y="2" width="36" height="36"/>
</svg>""",
        encoding="utf-8",
    )
    settings = Settings(artifact_dir=tmp_path, profile="jingan")
    svc = PenService(settings)
    job = svc.draw_svg(str(svg), paper="A6", dry_run=True)
    assert job.ok and job.dry_run
