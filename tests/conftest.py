"""
Shared pytest fixtures and configuration.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURE_ALBUM = Path(__file__).parent / "fixtures" / "e2e_album"
FIXTURE_ALBUM_NEW_FORMAT = Path(__file__).parent / "fixtures" / "e2e_album_new_format"


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


@pytest.fixture(scope="class")
def temp_album(tmp_path_factory):
    """Copy the fixture album to a fresh temp directory once per test class.

    Class scope means every test *method* in a class shares one copy, which
    avoids re-copying ~17 MB of fixture files for each method.  It is safe
    because _make_args() defaults to force=True, so every _run_folder() call
    always re-processes the files regardless of existing metadata.

    The one exception — TestAlreadyProcessed — supplies its own fixture copy
    so it can control the force flag independently.
    """
    album_dir = tmp_path_factory.mktemp("e2e_album")
    shutil.copytree(FIXTURE_ALBUM, album_dir / "album")
    return album_dir / "album"


@pytest.fixture(scope="class")
def temp_album_new_format(tmp_path_factory):
    """Class-scoped copy of the new-format fixture album.

    Same shape as `temp_album` but for the May-2026+ Takeout sidecar format
    (`.supplemental-metadata.json` family). Used by tests in
    test_e2e_new_format.py.
    """
    album_dir = tmp_path_factory.mktemp("e2e_album_new_format")
    shutil.copytree(FIXTURE_ALBUM_NEW_FORMAT, album_dir / "album")
    return album_dir / "album"


_MEDIA_EXTS = {".png", ".heic", ".webp", ".jpeg", ".jpg", ".mp4", ".mov", ".gif"}


@pytest.fixture
def fresh_album(tmp_path):
    """Fresh per-function copy used by tests that need to control force=False.

    After copying, the two tags that batch_read_processed() checks
    (DateTimeOriginal and QuickTime:CreateDate) are stripped from every media
    file using exiftool.  This guarantees that a force=False first run sees
    genuinely unprocessed files — even if the source fixture files had those
    tags written into them by an earlier real galbum run.

    Without this step, a force=False run would silently skip everything and
    tests would fail on their pre-condition assert.
    """
    album_dir = tmp_path / "e2e_album"
    shutil.copytree(FIXTURE_ALBUM, album_dir)

    media_files = [
        str(f) for f in album_dir.iterdir()
        if f.is_file() and f.suffix.lower() in _MEDIA_EXTS
    ]
    if media_files:
        # Strip every tag that galbum writes so that any test using this
        # fixture can assert the "before" state is empty/absent.
        subprocess.run(
            [
                "exiftool",
                # timestamps
                "-DateTimeOriginal=",
                "-CreateDate=",
                "-ModifyDate=",
                "-XMP:DateTimeOriginal=",
                "-XMP:CreateDate=",
                "-QuickTime:CreateDate=",
                "-QuickTime:ModifyDate=",
                "-QuickTime:TrackCreateDate=",
                "-QuickTime:TrackModifyDate=",
                "-QuickTime:MediaCreateDate=",
                "-QuickTime:MediaModifyDate=",
                "-Keys:CreationDate=",
                # GPS
                "-GPSLatitude=",
                "-GPSLongitude=",
                "-GPSAltitude=",
                "-GPSLatitudeRef=",
                "-GPSLongitudeRef=",
                "-XMP:GPSLatitude=",
                "-XMP:GPSLongitude=",
                "-XMP:GPSAltitude=",
                "-GPSCoordinates=",
                # description / rating
                "-XMP:Description=",
                "-ImageDescription=",
                "-XMP:Rating=",
                "-overwrite_original",
                *media_files,
            ],
            capture_output=True,
            check=False,
        )

    return album_dir
