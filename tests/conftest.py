from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"


def sample_report(name: str) -> Path:
    """Path to a local, gitignored sample report; skips the test if it isn't present."""
    matches = sorted((SAMPLES / name).glob("*.Report")) if (SAMPLES / name).is_dir() else []
    if not matches:
        pytest.skip(f"sample {name!r} not present under samples/ (local-only, gitignored)")
    return matches[0]


@pytest.fixture
def retail_report() -> Path:
    return sample_report("retail-analysis")
