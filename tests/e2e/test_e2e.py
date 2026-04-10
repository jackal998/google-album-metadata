"""
End-to-end tests for sync_takeout.py.

These tests:
  1. Copy the fixture album (tests/fixtures/e2e_album/) to a fresh temp dir
     per test run — original fixture files are NEVER modified.
  2. Run process_folder() against the copy.
  3. Read metadata back with exiftool and assert the expected values.

All fixture JSON sidecars contain controlled, clearly "wrong" metadata
(timestamp = 2021-01-01 00:00:00 UTC, GPS = Tokyo) so that assertions are
unambiguous — the script must have written them.

Mark: @pytest.mark.e2e
Requires: exiftool on PATH (installed in CI via apt-get install libimage-exiftool-perl)
"""

import argparse
import logging
import subprocess
from pathlib import Path

import pytest

from sync_takeout import ExiftoolProcess, process_folder

# ---------------------------------------------------------------------------
# Shared constants — must match tests/fixtures/e2e_album/*.json
# ---------------------------------------------------------------------------

FIXTURE_TS_DATE = "2021:01:01"           # from timestamp 1609459200 (UTC)
FIXTURE_GPS_LAT = 35.6762               # Tokyo latitude
FIXTURE_GPS_LON = 139.6503              # Tokyo longitude
FIXTURE_DESCRIPTION = "e2e test fixture"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_tag(path: Path, tag: str) -> str:
    """Read a single exiftool tag value from a file.
    -n forces numeric output (e.g. decimal degrees instead of '35 deg 40' 34.32" N').
    """
    result = subprocess.run(
        ["exiftool", "-n", "-s3", f"-{tag}", str(path)],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def _make_args(**overrides) -> argparse.Namespace:
    """Return a minimal args namespace suitable for process_folder()."""
    defaults = dict(force=True, dry_run=False, backup=False, no_file_dates=True)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _run_folder(folder: Path, **arg_overrides):
    """Run process_folder() on folder and return (orphan_list, fail_list)."""
    orphan_list: list = []
    fail_list:   list = []
    args = _make_args(**arg_overrides)
    log  = logging.getLogger("e2e")
    with ExiftoolProcess() as et:
        process_folder(folder, args, et, log, orphan_list, fail_list)
    return orphan_list, fail_list

# ---------------------------------------------------------------------------
# Fixture: temp_album is provided by conftest.py
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Step 1 — Exact match (PNG)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestExactMatchPng:
    def test_timestamp_written(self, temp_album):
        _run_folder(temp_album)
        dt = _read_tag(temp_album / "IMG_0006.PNG", "XMP:DateTimeOriginal")
        assert FIXTURE_TS_DATE in dt, f"Expected date {FIXTURE_TS_DATE!r} in {dt!r}"

    def test_gps_written(self, temp_album):
        _run_folder(temp_album)
        lat = _read_tag(temp_album / "IMG_0006.PNG", "XMP:GPSLatitude")
        assert lat, "GPSLatitude should be set"
        assert float(lat) == pytest.approx(FIXTURE_GPS_LAT, abs=0.01)

    def test_description_written(self, temp_album):
        _run_folder(temp_album)
        desc = _read_tag(temp_album / "IMG_0006.PNG", "XMP:Description")
        assert desc == FIXTURE_DESCRIPTION


# ---------------------------------------------------------------------------
# Step 1 — Exact match (WEBP)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestExactMatchWebp:
    def test_timestamp_written(self, temp_album):
        _run_folder(temp_album)
        dt = _read_tag(temp_album / "IMG_3846.WEBP", "XMP:DateTimeOriginal")
        assert FIXTURE_TS_DATE in dt

    def test_gps_written(self, temp_album):
        _run_folder(temp_album)
        lat = _read_tag(temp_album / "IMG_3846.WEBP", "XMP:GPSLatitude")
        assert lat
        assert float(lat) == pytest.approx(FIXTURE_GPS_LAT, abs=0.01)


# ---------------------------------------------------------------------------
# Step 1 — Exact match (JPEG, favorited=True)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestExactMatchJpeg:
    def test_timestamp_written(self, temp_album):
        _run_folder(temp_album)
        dt = _read_tag(temp_album / "IMG_4474_OZ1We__HD.jpeg", "DateTimeOriginal")
        assert FIXTURE_TS_DATE in dt

    def test_gps_written(self, temp_album):
        _run_folder(temp_album)
        lat = _read_tag(temp_album / "IMG_4474_OZ1We__HD.jpeg", "GPSLatitude")
        assert lat
        assert float(lat) == pytest.approx(FIXTURE_GPS_LAT, abs=0.01)

    def test_favorited_sets_rating_5(self, temp_album):
        _run_folder(temp_album)
        rating = _read_tag(temp_album / "IMG_4474_OZ1We__HD.jpeg", "XMP:Rating")
        assert rating == "5", f"Expected rating=5, got {rating!r}"


# ---------------------------------------------------------------------------
# Step 2 — Duplicate-number reordering (IMG_9556(1).HEIC → IMG_9556.HEIC(1).json)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestDuplicateNumber:
    def test_base_file_exact_match(self, temp_album):
        _run_folder(temp_album)
        dt = _read_tag(temp_album / "IMG_9556.HEIC", "DateTimeOriginal")
        assert FIXTURE_TS_DATE in dt

    def test_duplicate_1_matched_via_reorder(self, temp_album):
        _run_folder(temp_album)
        dt = _read_tag(temp_album / "IMG_9556(1).HEIC", "DateTimeOriginal")
        assert FIXTURE_TS_DATE in dt, \
            f"IMG_9556(1).HEIC should have been matched via step-2 duplicate reorder"


# ---------------------------------------------------------------------------
# Step 3 — Live-photo video orphan (IMG_9556(1).MP4 → IMG_9556.HEIC(1).json)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestLivePhotoVideo:
    def test_mp4_matched_via_heic_json(self, temp_album):
        _run_folder(temp_album)
        dt = _read_tag(temp_album / "IMG_9556(1).MP4", "XMP:DateTimeOriginal")
        assert FIXTURE_TS_DATE in dt, \
            "IMG_9556(1).MP4 should inherit metadata from IMG_9556.HEIC(1).json"


# ---------------------------------------------------------------------------
# Step 4 — Edited-photo fallback (IMG_3818-已編輯.HEIC → IMG_3818.HEIC.json)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestEditedFallback:
    def test_edited_file_matched_via_clean_stem(self, temp_album):
        _run_folder(temp_album)
        edited = temp_album / "IMG_3818-已編輯.HEIC"
        dt = _read_tag(edited, "DateTimeOriginal")
        assert FIXTURE_TS_DATE in dt, \
            "Edited HEIC should have been matched to IMG_3818.HEIC.json"

    def test_original_also_matched(self, temp_album):
        _run_folder(temp_album)
        dt = _read_tag(temp_album / "IMG_3818.HEIC", "DateTimeOriginal")
        assert FIXTURE_TS_DATE in dt


# ---------------------------------------------------------------------------
# Orphan — file with no JSON companion ends up in orphan_list
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestOrphan:
    def test_orphan_file_reported(self, temp_album):
        orphan_list, fail_list = _run_folder(temp_album)
        orphan_paths = [Path(p).name for p in orphan_list]
        assert "ORPHAN_NO_JSON.png" in orphan_paths, \
            f"Expected ORPHAN_NO_JSON.png in orphan list; got {orphan_paths}"

    def test_orphan_file_not_in_fail_list(self, temp_album):
        orphan_list, fail_list = _run_folder(temp_album)
        fail_names = [Path(p).name for p in fail_list]
        assert "ORPHAN_NO_JSON.png" not in fail_names


# ---------------------------------------------------------------------------
# Skip-list files — Thumbs.db and failed_inserting_exif.txt are ignored
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestSkipFiles:
    def test_thumbs_db_not_in_orphan(self, temp_album):
        orphan_list, _ = _run_folder(temp_album)
        orphan_names = [Path(p).name for p in orphan_list]
        assert "Thumbs.db" not in orphan_names

    def test_failed_inserting_exif_txt_not_in_orphan(self, temp_album):
        orphan_list, _ = _run_folder(temp_album)
        orphan_names = [Path(p).name for p in orphan_list]
        assert "failed_inserting_exif.txt" not in orphan_names


# ---------------------------------------------------------------------------
# Dry-run mode — no metadata should be written
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestDryRun:
    def test_dry_run_does_not_modify_files(self, temp_album):
        # Read original timestamp before dry run
        before = _read_tag(temp_album / "IMG_0006.PNG", "XMP:DateTimeOriginal")
        _run_folder(temp_album, dry_run=True)
        after = _read_tag(temp_album / "IMG_0006.PNG", "XMP:DateTimeOriginal")
        assert before == after, \
            "Dry-run should not write any metadata"

    def test_dry_run_returns_no_failures(self, temp_album):
        _, fail_list = _run_folder(temp_album, dry_run=True)
        assert fail_list == []


# ---------------------------------------------------------------------------
# Source fixture files remain untouched (paranoia check)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestSourceFilesUntouched:
    """
    Verify that the test never writes to the original fixture directory.
    The temp_album fixture copies files to tmp_path, so originals should
    never be modified — but we assert it explicitly for peace of mind.
    """

    FIXTURE_ALBUM = Path(__file__).parent.parent / "fixtures" / "e2e_album"

    def test_fixture_png_mtime_unchanged(self, temp_album):
        original = self.FIXTURE_ALBUM / "IMG_0006.PNG"
        mtime_before = original.stat().st_mtime
        _run_folder(temp_album)
        mtime_after = original.stat().st_mtime
        assert mtime_before == mtime_after, \
            "Source fixture file was modified — this should never happen"
