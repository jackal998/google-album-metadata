"""
Unit tests for parse_media_filename().

Covers:
  - Plain stem
  - Duplicate number  (N) suffix in stem
  - Every edited suffix (Chinese and English variants)
  - Duplicate + edited combined
  - Various media extensions, case variations
"""

from pathlib import Path

import pytest

from galbum import parse_media_filename


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def p(name: str) -> Path:
    """Shorthand: build a Path from a bare filename string."""
    return Path(name)


# ---------------------------------------------------------------------------
# Plain filenames
# ---------------------------------------------------------------------------

class TestPlainFilenames:
    def test_simple_heic(self):
        mf = parse_media_filename(p("IMG_9556.HEIC"))
        assert mf.base_stem == "IMG_9556"
        assert mf.number is None
        assert mf.suffix == ".HEIC"
        assert mf.is_edited is False
        assert mf.clean_stem == "IMG_9556"

    def test_simple_jpeg_lowercase(self):
        mf = parse_media_filename(p("photo.jpg"))
        assert mf.base_stem == "photo"
        assert mf.suffix == ".jpg"
        assert mf.number is None
        assert mf.is_edited is False

    def test_simple_mp4(self):
        mf = parse_media_filename(p("IMG_1048.MOV"))
        assert mf.base_stem == "IMG_1048"
        assert mf.suffix == ".MOV"
        assert mf.number is None

    def test_filename_with_underscores_and_hyphens(self):
        mf = parse_media_filename(p("IMG_4474_OZ1We__HD.jpeg"))
        assert mf.base_stem == "IMG_4474_OZ1We__HD"
        assert mf.number is None
        assert mf.is_edited is False

    def test_numeric_only_stem(self):
        mf = parse_media_filename(p("510289876210942038.mp4"))
        assert mf.base_stem == "510289876210942038"
        assert mf.number is None

    def test_uuid_stem(self):
        name = "9A42C069-94CF-4638-B96A-913FA5E2659D-48315-0000.mov"
        mf = parse_media_filename(p(name))
        assert mf.suffix == ".mov"
        assert mf.number is None
        assert mf.is_edited is False


# ---------------------------------------------------------------------------
# Duplicate-number suffix  IMG_xxx(N).EXT
# ---------------------------------------------------------------------------

class TestDuplicateNumbers:
    def test_duplicate_1(self):
        mf = parse_media_filename(p("IMG_9556(1).HEIC"))
        assert mf.base_stem == "IMG_9556"
        assert mf.number == 1
        assert mf.suffix == ".HEIC"

    def test_duplicate_2(self):
        mf = parse_media_filename(p("IMG_9556(2).HEIC"))
        assert mf.base_stem == "IMG_9556"
        assert mf.number == 2

    def test_duplicate_large_number(self):
        mf = parse_media_filename(p("IMG_9556(99).MP4"))
        assert mf.number == 99

    def test_duplicate_mp4_live_photo(self):
        mf = parse_media_filename(p("IMG_9556(1).MP4"))
        assert mf.base_stem == "IMG_9556"
        assert mf.number == 1
        assert mf.suffix == ".MP4"

    def test_parentheses_at_start_not_treated_as_duplicate(self):
        # (1)IMG.HEIC — the (1) is at the start, not end of stem
        mf = parse_media_filename(p("(1)IMG.HEIC"))
        # DUPE_RE anchors to end of stem, so this should not match
        assert mf.base_stem == "(1)IMG"
        assert mf.number is None


# ---------------------------------------------------------------------------
# Edited suffixes
# ---------------------------------------------------------------------------

class TestEditedSuffixes:
    @pytest.mark.parametrize("suffix", [
        "-已編輯",
        "(已編輯)",
        "-edited",
        "-Edit",
        "_edited",
        " edited",
    ])
    def test_all_edited_variants(self, suffix):
        fname = f"IMG_3818{suffix}.HEIC"
        mf = parse_media_filename(p(fname))
        assert mf.is_edited is True, f"Expected is_edited=True for {fname!r}"
        assert mf.clean_stem == "IMG_3818"
        assert mf.base_stem == f"IMG_3818{suffix}"

    def test_non_edited_file_unchanged(self):
        mf = parse_media_filename(p("IMG_3818.HEIC"))
        assert mf.is_edited is False
        assert mf.clean_stem == "IMG_3818"

    def test_edited_suffix_preserved_in_base_stem(self):
        mf = parse_media_filename(p("IMG_3818-已編輯.HEIC"))
        assert mf.base_stem == "IMG_3818-已編輯"
        assert mf.clean_stem == "IMG_3818"


# ---------------------------------------------------------------------------
# Duplicate + edited combined edge case
# ---------------------------------------------------------------------------

class TestDuplicateAndEdited:
    def test_duplicate_edited_chinese(self):
        # e.g. IMG_3818-已編輯(1).HEIC
        mf = parse_media_filename(p("IMG_3818-已編輯(1).HEIC"))
        assert mf.number == 1
        assert mf.base_stem == "IMG_3818-已編輯"
        assert mf.is_edited is True
        assert mf.clean_stem == "IMG_3818"
