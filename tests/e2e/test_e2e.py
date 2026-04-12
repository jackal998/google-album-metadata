"""
End-to-end tests for galbum.

These tests:
  1. Copy the fixture album (tests/fixtures/e2e_album/) to a fresh temp dir
     once per test class — original fixture files are NEVER modified.
  2. Run process_folder() against the copy.
  3. Read metadata back with exiftool and assert the expected values.

All fixture JSON sidecars contain controlled, clearly "wrong" metadata
(timestamp = 2021-01-01 00:00:00 UTC, GPS = Tokyo) so that assertions are
unambiguous — the script must have written them, not left-over originals.

Fixtures:
  temp_album  — class-scoped copy; force=True always re-processes (safe to share)
  fresh_album — function-scoped copy; used by tests that need force=False

Mark: @pytest.mark.e2e
Requires: exiftool on PATH
"""

import argparse
import json
import logging
import subprocess
from pathlib import Path

import pytest

from galbum import ExiftoolProcess, process_folder

# ---------------------------------------------------------------------------
# Shared constants — must match tests/fixtures/e2e_album/*.json
# ---------------------------------------------------------------------------

FIXTURE_UNIX_TS  = 1609459200            # 2021-01-01 00:00:00 UTC
FIXTURE_TS_DATE  = "2021:01:01"          # date portion (same in UTC and JST)
FIXTURE_TS_UTC   = "2021:01:01 00:00:00" # exact UTC datetime (no offset)
FIXTURE_GPS_LAT  = 35.6762              # Tokyo latitude
FIXTURE_GPS_LON  = 139.6503             # Tokyo longitude
FIXTURE_DESCRIPTION = "e2e test fixture"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_tag(path: Path, tag: str) -> str:
    """Read a single exiftool tag value from a file.
    -n forces numeric output (e.g. decimal degrees instead of '35 deg 40.3" N').
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
# Fixtures: temp_album (class-scoped) and fresh_album (function-scoped)
# are provided by conftest.py
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
    MP4 = "IMG_9556(1).MP4"

    def test_mp4_matched_via_heic_json(self, temp_album):
        _run_folder(temp_album)
        dt = _read_tag(temp_album / self.MP4, "XMP:DateTimeOriginal")
        assert FIXTURE_TS_DATE in dt, \
            "IMG_9556(1).MP4 should inherit metadata from IMG_9556.HEIC(1).json"

    def test_xmp_create_date_written(self, temp_album):
        _run_folder(temp_album)
        dt = _read_tag(temp_album / self.MP4, "XMP:CreateDate")
        assert FIXTURE_TS_DATE in dt, "XMP:CreateDate should be written for video"

    def test_quicktime_create_date_is_utc(self, temp_album):
        """QuickTime:CreateDate must be stored as UTC with no timezone offset.

        The fixture GPS resolves to JST (+09:00), so local time is 09:00:00 and
        UTC is 00:00:00.  The stored value must be the UTC one — if local time
        leaked in, players and Windows Explorer would double-shift by +09:00.
        """
        _run_folder(temp_album)
        val = _read_tag(temp_album / self.MP4, "QuickTime:CreateDate")
        assert val == FIXTURE_TS_UTC, (
            f"QuickTime:CreateDate should be UTC {FIXTURE_TS_UTC!r}, got {val!r}. "
            "Local time must NOT be stored here."
        )

    def test_keys_creation_date_has_offset(self, temp_album):
        """Keys:CreationDate (Apple atom) must carry a timezone offset.

        This tag supports full ISO 8601 with offset, so unlike QuickTime:CreateDate
        it should include the local timezone — either +09:00 (JST if timezonefinder
        resolves the GPS) or +00:00 (UTC fallback).  Either way an offset must be
        present so the stored time is unambiguous.
        """
        _run_folder(temp_album)
        val = _read_tag(temp_album / self.MP4, "Keys:CreationDate")
        assert FIXTURE_TS_DATE in val, "Keys:CreationDate should contain the date"
        assert "+" in val or (len(val) > 19 and val[19] == "-"), \
            f"Keys:CreationDate should have a timezone offset, got {val!r}"

    def test_gps_coordinates_written(self, temp_album):
        _run_folder(temp_album)
        # GPSCoordinates is the QuickTime GPS field (signed decimal)
        coords = _read_tag(temp_album / self.MP4, "GPSCoordinates")
        assert coords, "GPSCoordinates should be written for video with GPS"

    def test_xmp_gps_written(self, temp_album):
        _run_folder(temp_album)
        lat = _read_tag(temp_album / self.MP4, "XMP:GPSLatitude")
        assert lat, "XMP:GPSLatitude should be written"
        assert float(lat) == pytest.approx(FIXTURE_GPS_LAT, abs=0.01)


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
    def test_dry_run_does_not_modify_files(self, fresh_album):
        """Dry-run must not change metadata that was written by a prior real run.

        We do a real run first so there is a known, non-empty value to guard —
        if the 'before' baseline were empty (unprocessed file) the assertion
        would pass vacuously even if dry-run silently wrote something.
        """
        # Real run: write metadata so there is a known value on disk
        _run_folder(fresh_album, force=True)
        written = _read_tag(fresh_album / "IMG_0006.PNG", "XMP:DateTimeOriginal")
        assert written, "Pre-condition: real run must have written a timestamp"

        # Dry-run: must not alter that value
        _run_folder(fresh_album, dry_run=True)
        after = _read_tag(fresh_album / "IMG_0006.PNG", "XMP:DateTimeOriginal")
        assert after == written, (
            f"Dry-run should not modify already-written metadata. "
            f"Before: {written!r}  After: {after!r}"
        )

    def test_dry_run_returns_no_failures(self, fresh_album):
        _, fail_list = _run_folder(fresh_album, dry_run=True)
        assert fail_list == []


# ---------------------------------------------------------------------------
# Already-processed skip path  (tests batch_read_processed + processed_set)
# Uses fresh_album (function-scoped) so force=False is meaningful.
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestAlreadyProcessed:
    def test_second_run_skips_processed_files(self, fresh_album):
        """After a first run, a second run WITHOUT --force should skip all files
        that already have DateTimeOriginal / QuickTime:CreateDate set.

        We verify this by tampering with one JSON file between the two runs:
        if the second run re-processed the file it would pick up the new
        timestamp; if it correctly skips, the old written value is preserved.
        """
        # First run — force=True to reliably write metadata to every file.
        # (force=False would skip files whose tags survived the fixture strip,
        # making the 2021 pre-condition unreliable.)
        _run_folder(fresh_album, force=True)

        # Tamper: change the timestamp in one JSON to a clearly different value
        json_path = fresh_album / "IMG_0006.PNG.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        original_ts = data["photoTakenTime"]["timestamp"]
        data["photoTakenTime"]["timestamp"] = "978307200"   # 2001-01-01 00:00:00 UTC
        json_path.write_text(json.dumps(data), encoding="utf-8")

        # Second run — should skip the already-processed file
        _run_folder(fresh_album, force=False)

        # The PNG should still have the ORIGINAL date (not 2001)
        dt = _read_tag(fresh_album / "IMG_0006.PNG", "XMP:DateTimeOriginal")
        assert "2021:01:01" in dt, (
            f"Expected original 2021 date to be preserved (file should have been "
            f"skipped on second run), but got: {dt!r}"
        )
        assert "2001" not in dt, \
            "Tampered 2001 timestamp leaked in — file was not skipped as expected"

        # Restore JSON for cleanliness
        data["photoTakenTime"]["timestamp"] = original_ts
        json_path.write_text(json.dumps(data), encoding="utf-8")

    def test_force_overwrites_stale_metadata(self, fresh_album):
        """--force must re-process files that already have metadata written.

        This is the mirror of test_second_run_skips_processed_files:
        after a first run, tamper the JSON, then run again with force=True —
        the new (tampered) timestamp must appear in the file, proving --force
        bypassed the batch_read_processed skip gate.
        """
        # First run: force=True to reliably write the fixture timestamp to every file.
        _run_folder(fresh_album, force=True)
        dt_first = _read_tag(fresh_album / "IMG_0006.PNG", "XMP:DateTimeOriginal")
        assert "2021:01:01" in dt_first, f"Pre-condition failed: got {dt_first!r}"

        # Tamper JSON to a clearly different year
        json_path = fresh_album / "IMG_0006.PNG.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        original_ts = data["photoTakenTime"]["timestamp"]
        data["photoTakenTime"]["timestamp"] = "978307200"   # 2001-01-01 00:00:00 UTC
        json_path.write_text(json.dumps(data), encoding="utf-8")

        # Second run with --force: must overwrite despite file already being tagged
        _run_folder(fresh_album, force=True)

        dt_second = _read_tag(fresh_album / "IMG_0006.PNG", "XMP:DateTimeOriginal")
        assert "2001:01:01" in dt_second, (
            f"--force should have re-processed and written the 2001 date, "
            f"but got: {dt_second!r}"
        )
        assert "2021" not in dt_second, \
            "Old 2021 date still present — --force did not overwrite"

        # Restore JSON
        data["photoTakenTime"]["timestamp"] = original_ts
        json_path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# Write-proof — explicit before → after transformation checks
#
# Uses fresh_album (which strips all galbum-written tags), so the "before"
# state is guaranteed empty.  Proves galbum actually changed the file rather
# than just finding a pre-existing correct value.
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestWriteProof:
    """Each test reads a tag BEFORE the run (asserts absent), runs galbum,
    then reads AFTER (asserts expected value is now present).

    This is the strongest form of assertion: it proves a transformation
    happened, not just that the end-state happens to match.
    """

    def test_png_timestamp_written_from_empty(self, fresh_album):
        # Before: tag must be absent (fresh_album stripped it)
        before = _read_tag(fresh_album / "IMG_0006.PNG", "XMP:DateTimeOriginal")
        assert not before, \
            f"Pre-condition: XMP:DateTimeOriginal should be absent before run, got {before!r}"

        _run_folder(fresh_album, force=True)

        after = _read_tag(fresh_album / "IMG_0006.PNG", "XMP:DateTimeOriginal")
        assert FIXTURE_TS_DATE in after, \
            f"Expected {FIXTURE_TS_DATE!r} written by galbum, got {after!r}"

    def test_jpeg_gps_written_from_empty(self, fresh_album):
        # Before: GPS must be absent
        before = _read_tag(fresh_album / "IMG_4474_OZ1We__HD.jpeg", "GPSLatitude")
        assert not before, \
            f"Pre-condition: GPSLatitude should be absent before run, got {before!r}"

        _run_folder(fresh_album, force=True)

        after = _read_tag(fresh_album / "IMG_4474_OZ1We__HD.jpeg", "GPSLatitude")
        assert after, "GPSLatitude should be written"
        assert float(after) == pytest.approx(FIXTURE_GPS_LAT, abs=0.01), \
            f"Expected Tokyo lat ~{FIXTURE_GPS_LAT}, got {after!r}"

    def test_video_quicktime_utc_written_from_empty(self, fresh_album):
        # Before: QuickTime:CreateDate must be absent or zeroed.
        # MP4 containers store this field structurally; exiftool cannot truly
        # remove it — stripping zeroes it to "0000:00:00 00:00:00" instead.
        # batch_read_processed already treats that as "unprocessed" (valid()
        # rejects it), so both "" and the null date are acceptable here.
        before = _read_tag(fresh_album / "IMG_9556(1).MP4", "QuickTime:CreateDate")
        assert before in ("", "0000:00:00 00:00:00"), \
            f"Pre-condition: QuickTime:CreateDate should be absent/zeroed before run, got {before!r}"

        _run_folder(fresh_album, force=True)

        after = _read_tag(fresh_album / "IMG_9556(1).MP4", "QuickTime:CreateDate")
        assert after == FIXTURE_TS_UTC, (
            f"QuickTime:CreateDate should be UTC {FIXTURE_TS_UTC!r}, got {after!r}. "
            "Local time must NOT be stored here."
        )


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
