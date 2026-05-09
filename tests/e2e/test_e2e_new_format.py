"""
End-to-end tests for the May 2026+ Google Takeout format.

These mirror the legacy `test_e2e.py` suite but exercise:

  - The new ``<media>.<ext>.supplemental-metadata.json`` sidecar suffix
  - All five observed truncation variants of that suffix
  - The heavily-truncated case where the JSON's filename is too short to
    recover the original media name (``title`` field is authoritative)
  - The new ``archived`` field (currently ignored, must not crash)
  - Sidecars without the legacy ``geoDataExif`` field (the May 2026+
    schema makes ``geoData`` the primary GPS source)

Fixture layout (`tests/fixtures/e2e_album_new_format/`):

  IMG_FULL.HEIC                                       — full new suffix
    IMG_FULL.HEIC.supplemental-metadata.json
  IMG_TRUNC.JPEG                                      — one-char-trim suffix
    IMG_TRUNC.JPEG.supplemental-metadat.json
  IMG_DUPE.HEIC                                       — exact match dupe
    IMG_DUPE.HEIC.supplemental-metadata.json
  IMG_DUPE(1).HEIC + IMG_DUPE(1).MP4                  — duplicate-reorder + live-photo
    IMG_DUPE.HEIC(1).supplemental-metadata.json
  VERY_LONG_FILENAME_TRUNCATED.HEIC                   — heavy truncation (title-match)
    VERY_LONG_FILENAME_TRUNCAT.json
  IMG_ARCHIVED.PNG                                    — archived field, no geoDataExif
    IMG_ARCHIVED.PNG.supplemental-metadata.json
  ORPHAN_NEW_NO_JSON.png                              — orphan
"""

import argparse
import logging
import subprocess
from pathlib import Path

import pytest

from galbum import ExiftoolProcess, process_folder

# ---------------------------------------------------------------------------
# Shared constants — must match every fixture JSON in e2e_album_new_format/
# ---------------------------------------------------------------------------

FIXTURE_TS_DATE = "2021:01:01"
FIXTURE_GPS_LAT = 35.6762
FIXTURE_GPS_LON = 139.6503
FIXTURE_DESCRIPTION_PREFIX = "e2e new-format test:"


def _read_tag(path: Path, tag: str) -> str:
    result = subprocess.run(
        ["exiftool", "-n", "-s3", f"-{tag}", str(path)],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def _make_args(**overrides) -> argparse.Namespace:
    defaults = dict(force=True, dry_run=False, backup=False, no_file_dates=True)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _run_folder(folder: Path, **arg_overrides):
    orphan_list: list = []
    fail_list: list = []
    args = _make_args(**arg_overrides)
    log = logging.getLogger("e2e_new")
    with ExiftoolProcess() as et:
        process_folder(folder, args, et, log, orphan_list, fail_list)
    return orphan_list, fail_list


# ---------------------------------------------------------------------------
# Full suffix: <media>.<ext>.supplemental-metadata.json
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestFullSupplementalSuffix:
    def test_timestamp_written(self, temp_album_new_format):
        _run_folder(temp_album_new_format)
        dt = _read_tag(temp_album_new_format / "IMG_FULL.HEIC", "DateTimeOriginal")
        assert FIXTURE_TS_DATE in dt, f"got {dt!r}"

    def test_gps_written(self, temp_album_new_format):
        _run_folder(temp_album_new_format)
        lat = _read_tag(temp_album_new_format / "IMG_FULL.HEIC", "GPSLatitude")
        assert lat and float(lat) == pytest.approx(FIXTURE_GPS_LAT, abs=0.01)

    def test_description_written(self, temp_album_new_format):
        _run_folder(temp_album_new_format)
        desc = _read_tag(temp_album_new_format / "IMG_FULL.HEIC", "ImageDescription")
        assert FIXTURE_DESCRIPTION_PREFIX in desc, f"got {desc!r}"


# ---------------------------------------------------------------------------
# Truncated suffix: .supplemental-metadat.json (one char trimmed)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestTruncatedSuffix:
    def test_timestamp_written(self, temp_album_new_format):
        _run_folder(temp_album_new_format)
        dt = _read_tag(temp_album_new_format / "IMG_TRUNC.JPEG", "DateTimeOriginal")
        assert FIXTURE_TS_DATE in dt, f"got {dt!r}"

    def test_gps_written(self, temp_album_new_format):
        _run_folder(temp_album_new_format)
        lat = _read_tag(temp_album_new_format / "IMG_TRUNC.JPEG", "GPSLatitude")
        assert lat and float(lat) == pytest.approx(FIXTURE_GPS_LAT, abs=0.01)

    def test_favorited_writes_rating(self, temp_album_new_format):
        # Truncated-suffix fixture has favorited=true → expect XMP:Rating=5
        _run_folder(temp_album_new_format)
        rating = _read_tag(temp_album_new_format / "IMG_TRUNC.JPEG", "XMP:Rating")
        assert rating == "5", f"expected Rating=5, got {rating!r}"


# ---------------------------------------------------------------------------
# Duplicate-number reorder + new suffix
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestDuplicateReorderNewFormat:
    def test_exact_dupe_timestamp(self, temp_album_new_format):
        # IMG_DUPE.HEIC ↔ IMG_DUPE.HEIC.supplemental-metadata.json (Step 1: exact)
        _run_folder(temp_album_new_format)
        dt = _read_tag(temp_album_new_format / "IMG_DUPE.HEIC", "DateTimeOriginal")
        assert FIXTURE_TS_DATE in dt

    def test_dupe_one_timestamp(self, temp_album_new_format):
        # IMG_DUPE(1).HEIC ↔ IMG_DUPE.HEIC(1).supplemental-metadata.json (Step 2)
        _run_folder(temp_album_new_format)
        dt = _read_tag(temp_album_new_format / "IMG_DUPE(1).HEIC", "DateTimeOriginal")
        assert FIXTURE_TS_DATE in dt

    def test_live_photo_video_finds_dupe_sidecar(self, temp_album_new_format):
        # IMG_DUPE(1).MP4 has no sidecar of its own; it should match
        # IMG_DUPE.HEIC(1).supplemental-metadata.json via Step 3 (live_photo).
        _run_folder(temp_album_new_format)
        dt = _read_tag(temp_album_new_format / "IMG_DUPE(1).MP4", "QuickTime:CreateDate")
        assert FIXTURE_TS_DATE in dt, f"got {dt!r}"


# ---------------------------------------------------------------------------
# Real-world Google (N) placement — (N) lives INSIDE the suffix, between
# `metadata` and `.json`:
#     IMG_X.HEIC.supplemental-metadata(1).json
# Distinct from the IMG_DUPE fixture above which uses .HEIC(1).supplemental-...
# Both placements work post-PR-D, but real-world Google output is this one
# (verified against the May-2026 Takeout export — see PR-D for the regression
# this fixture pins down).
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestRealGoogleDupePlacement:
    def test_original_resolves_via_exact(self, temp_album_new_format):
        # IMG_INLINE_DUPE.HEIC + .HEIC.supplemental-metadata.json (Step 1: exact)
        _run_folder(temp_album_new_format)
        dt = _read_tag(temp_album_new_format / "IMG_INLINE_DUPE.HEIC",
                       "DateTimeOriginal")
        assert FIXTURE_TS_DATE in dt

    def test_duplicate_resolves_via_step2_with_inline_n(self, temp_album_new_format):
        # IMG_INLINE_DUPE(1).HEIC + .HEIC.supplemental-metadata(1).json (Step 2)
        # Pre-PR-D this would be orphaned: _strip_json_suffix only stripped
        # `.json` for this filename pattern, leaving `…supplemental-metadata(1)`
        # as the implied-name key — never matching anything Step 2 looks up.
        _run_folder(temp_album_new_format)
        dt = _read_tag(temp_album_new_format / "IMG_INLINE_DUPE(1).HEIC",
                       "DateTimeOriginal")
        assert FIXTURE_TS_DATE in dt, (
            f"IMG_INLINE_DUPE(1).HEIC should resolve to its dupe sidecar; got {dt!r}"
        )


# ---------------------------------------------------------------------------
# Heavy truncation: JSON filename too short to derive media name from
# (title field is authoritative — Step 5 title_match)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestHeavilyTruncatedJsonName:
    def test_title_match_writes_timestamp(self, temp_album_new_format):
        # JSON name `VERY_LONG_FILENAME_TRUNCAT.json` cannot be matched by
        # filename pattern; only the title field carrying the full
        # `VERY_LONG_FILENAME_TRUNCATED.HEIC` makes this work.
        _run_folder(temp_album_new_format)
        dt = _read_tag(
            temp_album_new_format / "VERY_LONG_FILENAME_TRUNCATED.HEIC",
            "DateTimeOriginal",
        )
        assert FIXTURE_TS_DATE in dt, f"got {dt!r}"

    def test_title_match_writes_gps(self, temp_album_new_format):
        _run_folder(temp_album_new_format)
        lat = _read_tag(
            temp_album_new_format / "VERY_LONG_FILENAME_TRUNCATED.HEIC",
            "GPSLatitude",
        )
        assert lat and float(lat) == pytest.approx(FIXTURE_GPS_LAT, abs=0.01)


# ---------------------------------------------------------------------------
# Schema additions: `archived` field, missing `geoDataExif`
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestSchemaChanges:
    def test_archived_field_does_not_crash(self, temp_album_new_format):
        # IMG_ARCHIVED.PNG's JSON has `archived: true` and no `geoDataExif`.
        # The pipeline must process it normally; archived is currently ignored.
        _run_folder(temp_album_new_format)
        dt = _read_tag(temp_album_new_format / "IMG_ARCHIVED.PNG", "XMP:DateTimeOriginal")
        assert FIXTURE_TS_DATE in dt

    def test_geo_data_alone_still_resolves_gps(self, temp_album_new_format):
        # Same fixture: only `geoData` (no `geoDataExif`). GPS must still write.
        _run_folder(temp_album_new_format)
        lat = _read_tag(temp_album_new_format / "IMG_ARCHIVED.PNG", "XMP:GPSLatitude")
        assert lat and float(lat) == pytest.approx(FIXTURE_GPS_LAT, abs=0.01)

    def test_archived_does_not_set_rating(self, temp_album_new_format):
        # `archived` is a separate concept from `favorited`; it must NOT
        # produce a Rating tag (which would imply 5-star favorite).
        _run_folder(temp_album_new_format)
        rating = _read_tag(temp_album_new_format / "IMG_ARCHIVED.PNG", "XMP:Rating")
        assert rating == "", f"archived photo should not have XMP:Rating; got {rating!r}"


# ---------------------------------------------------------------------------
# Orphan handling
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestOrphanHandlingNewFormat:
    def test_orphan_listed(self, temp_album_new_format):
        orphan_list, _ = _run_folder(temp_album_new_format)
        # ORPHAN_NEW_NO_JSON.png has no sidecar in any suffix variant.
        assert any("ORPHAN_NEW_NO_JSON.png" in str(p) for p in orphan_list), \
            f"expected ORPHAN_NEW_NO_JSON.png in orphan_list, got {orphan_list!r}"
