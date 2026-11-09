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


def _real_reports() -> list[Path]:
    """Every sample's .Report folder, so tests that hold for any Desktop-saved report run on each."""
    if not SAMPLES.is_dir():
        return []
    return sorted(r for d in SAMPLES.iterdir() if d.is_dir() for r in d.glob("*.Report"))


@pytest.fixture(params=_real_reports() or [None],
                ids=lambda p: p.parent.name if p else "no-samples")
def real_report(request) -> Path:
    """Each local sample report in turn (see samples/README.md); skips when there are none."""
    if request.param is None:
        pytest.skip("no sample reports under samples/ (local-only, gitignored)")
    return request.param


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
