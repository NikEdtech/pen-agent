import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
# Prefer sibling checkout of grbl-pen-plotter during local Mac dev
sibling = ROOT.parent / "grbl-pen-plotter" / "src"
if sibling.is_dir():
    sys.path.insert(0, str(sibling))
