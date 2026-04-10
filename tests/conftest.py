"""
Shared pytest fixtures and configuration.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURE_ALBUM = Path(__file__).parent / "fixtures" / "e2e_album"


def _exiftool_available() -> bool:
    try:
        subprocess.run(["exiftool", "-ver"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


# Skip the entire e2e suite when exiftool is not on PATH
collect_ignore_glob: list = []
if not _exiftool_available():
    import warnings
    warnings.warn("exiftool not found — e2e tests will be skipped", stacklevel=1)


@pytest.fixture
def temp_album(tmp_path):
    """Copy the fixture album to a fresh temp directory for each test."""
    album_dir = tmp_path / "e2e_album"
    shutil.copytree(FIXTURE_ALBUM, album_dir)
    return album_dir
