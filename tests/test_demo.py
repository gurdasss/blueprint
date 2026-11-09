"""scripts/demo.sh, the end-to-end demo the user checked in Desktop, keeps working."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_demo_builds_checks_clean_and_is_idempotent(tmp_path: Path):
    env = {**os.environ, "DEMO": str(tmp_path / "demo"),
           "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}"}
    done = subprocess.run(["bash", str(ROOT / "scripts" / "demo.sh")], env=env, capture_output=True,
                          text=True, check=False, timeout=300)
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-3000:]
    assert "0 error(s)" in done.stdout
    assert "No changes from apply, fmt, theme or manifest." in done.stdout
    pages = list((tmp_path / "demo/project/Fixture.Report/definition/pages").iterdir())
    assert len([p for p in pages if p.is_dir()]) == 11  # fixture's Overview + 10 demo pages
