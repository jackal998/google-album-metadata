"""
Unit tests for find_json() — the 5-step JSON-matching algorithm.

The JsonIndex is constructed directly (no disk I/O) using fake Paths so that
these tests run without any fixture files.
"""

from pathlib import Path

import pytest

from galbum import (
    JsonIndex,
    MatchResult,
    find_json,
    parse_media_filename,
)


# ---------------------------------------------------------------------------
# Helper: build a lightweight JsonIndex from a list of JSON filenames
# ---------------------------------------------------------------------------

def _make_index(*json_names: str, titles: dict | None = None) -> JsonIndex:
    """
    Build a JsonIndex where every JSON 'file' is a fake Path under /fake/.
    Optionally supply extra title→Path entries in `titles`.
    """
    by_exact = {name: Path(f"/fake/{name}") for name in json_names}
    by_title = {k: Path(f"/fake/{v}") for k, v in (titles or {}).items()}
    # all_stems mirrors what build_json_index would compute
    all_stems: dict = {}
    for name, path in by_exact.items():
        # strip .json, then strip (N), keep base stem
        without_json = name[: -len(".json")]
        stem = Path(without_json).stem
        from galbum import DUPE_RE
        m = DUPE_RE.match(stem)
        stem = m.group(1) if m else stem
        all_stems.setdefault(stem, []).append(path)
    return JsonIndex(by_exact=by_exact, by_title=by_title, all_stems=all_stems)


def mf(name: str):
    return parse_media_filename(Path(name))


# ---------------------------------------------------------------------------
# Step 1 — Exact match
# ---------------------------------------------------------------------------

class TestStep1ExactMatch:
    def test_heic_exact(self):
        index = _make_index("IMG_9556.HEIC.json")
        result = find_json(mf("IMG_9556.HEIC"), index)
        assert result is not None
        assert result.match_type == "exact"
        assert result.json_path == Path("/fake/IMG_9556.HEIC.json")

    def test_png_exact(self):
        index = _make_index("IMG_0006.PNG.json")
        result = find_json(mf("IMG_0006.PNG"), index)
        assert result is not None
        assert result.match_type == "exact"

    def test_webp_exact(self):
        index = _make_index("IMG_3846.WEBP.json")
        result = find_json(mf("IMG_3846.WEBP"), index)
        assert result is not None
        assert result.match_type == "exact"

    def test_jpeg_with_special_chars(self):
        index = _make_index("IMG_4474_OZ1We__HD.jpeg.json")
        result = find_json(mf("IMG_4474_OZ1We__HD.jpeg"), index)
        assert result is not None
        assert result.match_type == "exact"

    def test_numeric_filename(self):
        index = _make_index("510289876210942038.mp4.json")
        result = find_json(mf("510289876210942038.mp4"), index)
        assert result is not None
        assert result.match_type == "exact"


# ---------------------------------------------------------------------------
# Step 2 — Duplicate number reordering
# ---------------------------------------------------------------------------

class TestStep2DuplicateReorder:
    def test_heic_duplicate_1(self):
        # IMG_9556(1).HEIC should find IMG_9556.HEIC(1).json
        index = _make_index("IMG_9556.HEIC(1).json")
        result = find_json(mf("IMG_9556(1).HEIC"), index)
        assert result is not None
        assert result.match_type == "duplicate"

    def test_heic_duplicate_2(self):
        index = _make_index("IMG_9556.HEIC(2).json")
        result = find_json(mf("IMG_9556(2).HEIC"), index)
        assert result is not None
        assert result.match_type == "duplicate"

    def test_no_duplicate_number_doesnt_match_reorder(self):
        # Plain IMG_9556.HEIC should NOT match IMG_9556.HEIC(1).json via step 2
        index = _make_index("IMG_9556.HEIC(1).json")
        result = find_json(mf("IMG_9556.HEIC"), index)
        # Might match via step 5 title or fall through — not step 2
        if result is not None:
            assert result.match_type != "duplicate"


# ---------------------------------------------------------------------------
# Step 3 — Live-photo video orphan
# ---------------------------------------------------------------------------

class TestStep3LivePhotoVideo:
    @pytest.mark.parametrize("video_ext", [".MP4", ".MOV", ".M4V"])
    def test_video_finds_heic_companion(self, video_ext):
        index = _make_index("IMG_9556.HEIC.json")
        result = find_json(mf(f"IMG_9556{video_ext}"), index)
        assert result is not None
        assert result.match_type == "live_photo"

    def test_video_with_duplicate_number_finds_companion(self):
        # IMG_9556(1).MP4 → IMG_9556.HEIC(1).json
        index = _make_index("IMG_9556.HEIC(1).json")
        result = find_json(mf("IMG_9556(1).MP4"), index)
        assert result is not None
        assert result.match_type == "live_photo"

    def test_video_finds_jpg_companion(self):
        # FullSizeRender.MP4 → FullSizeRender.jpg.json
        index = _make_index("FullSizeRender.jpg.json")
        result = find_json(mf("FullSizeRender.MP4"), index)
        assert result is not None
        assert result.match_type == "live_photo"

    def test_image_file_not_treated_as_video(self):
        # .HEIC is not a video; step 3 should not fire
        index = _make_index("IMG_9556.jpg.json")
        result = find_json(mf("IMG_9556.HEIC"), index)
        # step 3 won't fire; might be None or matched via another step
        if result is not None:
            assert result.match_type != "live_photo"


# ---------------------------------------------------------------------------
# Step 4 — Edited-photo fallback
# ---------------------------------------------------------------------------

class TestStep4EditedFallback:
    def test_chinese_edited_suffix(self):
        # IMG_3818-已編輯.HEIC → IMG_3818.HEIC.json
        index = _make_index("IMG_3818.HEIC.json")
        result = find_json(mf("IMG_3818-已編輯.HEIC"), index)
        assert result is not None
        assert result.match_type == "edited_fallback"

    def test_english_edited_suffix(self):
        index = _make_index("IMG_3818.HEIC.json")
        result = find_json(mf("IMG_3818-edited.HEIC"), index)
        assert result is not None
        assert result.match_type == "edited_fallback"

    def test_edited_with_duplicate_number(self):
        # IMG_3818-已編輯(1).HEIC → IMG_3818.HEIC(1).json
        index = _make_index("IMG_3818.HEIC(1).json")
        result = find_json(mf("IMG_3818-已編輯(1).HEIC"), index)
        assert result is not None
        assert result.match_type == "edited_fallback"

    def test_non_edited_doesnt_trigger_fallback(self):
        # IMG_3818.HEIC → should not match edited_fallback
        index = _make_index("IMG_3818.HEIC.json")
        result = find_json(mf("IMG_3818.HEIC"), index)
        assert result is not None
        assert result.match_type == "exact"


# ---------------------------------------------------------------------------
# Step 5 — Title-field match (UUID truncation in both directions)
# ---------------------------------------------------------------------------

class TestStep5TitleMatch:
    def test_media_shorter_than_title(self):
        # Media file has a truncated name; JSON's title field has the full name
        truncated = "9A42C069-94CF-4638-B96A-913FA5E2659D-48315-0000.mov"
        full = "9A42C069-94CF-4638-B96A-913FA5E2659D-48315-00001E98C62951D8.mov"
        index = _make_index(
            "9A42C069-94CF-4638-B96A-913FA5E2659D-48315-000.json",
            titles={full: "9A42C069-94CF-4638-B96A-913FA5E2659D-48315-000.json"},
        )
        result = find_json(mf(truncated), index)
        assert result is not None
        assert result.match_type == "title_match"

    def test_short_stem_skips_title_check(self):
        # Stems ≤ 10 chars are excluded from step 5
        index = _make_index(titles={"short.jpg": "short.json"})
        result = find_json(mf("short.jpg"), index)
        assert result is None

    def test_prefix_below_threshold_no_match(self):
        # Files that share less than 80% prefix should NOT match
        index = _make_index(
            "AAAAAAAAAA_long_title.json",
            titles={"ZZZZZZZZZZZ_long_title.mov": "AAAAAAAAAA_long_title.json"},
        )
        result = find_json(mf("BBBBBBBBBB_long_other.mov"), index)
        # Should not match
        assert result is None or result.match_type != "title_match"


# ---------------------------------------------------------------------------
# No match at all
# ---------------------------------------------------------------------------

class TestNoMatch:
    def test_completely_unknown_file(self):
        index = _make_index("OTHER_FILE.HEIC.json")
        result = find_json(mf("IMG_UNKNOWN.HEIC"), index)
        assert result is None

    def test_empty_index(self):
        index = _make_index()
        result = find_json(mf("IMG_9556.HEIC"), index)
        assert result is None


# ---------------------------------------------------------------------------
# Priority: earlier steps win
# ---------------------------------------------------------------------------

class TestStepPriority:
    def test_exact_beats_duplicate(self):
        # Both an exact JSON and a duplicate-reorder JSON exist;
        # step 1 should win
        index = _make_index("IMG_9556.HEIC.json", "IMG_9556.HEIC(1).json")
        result = find_json(mf("IMG_9556.HEIC"), index)
        assert result is not None
        assert result.match_type == "exact"
