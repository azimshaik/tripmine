"""Smoke tests for the tripmine CLI scaffold."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "tripmine", *args],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"},
        cwd=ROOT,
    )


def test_version():
    r = run_cli("--version")
    assert r.returncode == 0
    assert "tripmine" in r.stdout


def test_extract_validates_input():
    r = run_cli("extract", "/nonexistent/path.zip")
    assert r.returncode == 1
    assert "not found" in r.stderr


def test_track_validates_input():
    r = run_cli("track", "/nonexistent/dir")
    assert r.returncode == 1
    assert "not found" in r.stderr
