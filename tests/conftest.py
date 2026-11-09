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


FIXTURES = ROOT / "fixtures"


def fixture_report(name: str) -> Path:
    """Path to a committed fixture's .Report folder (always present; see fixtures/README.md)."""
    [report] = sorted((FIXTURES / name).glob("*.Report"))
    return report


@pytest.fixture
def blank_fixture() -> Path:
    return fixture_report("01-blank-report")


@pytest.fixture
def card_chart_fixture() -> Path:
    return fixture_report("02-card-and-chart")
