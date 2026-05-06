"""
Unit tests for batch_read_processed() — JSON-based parsing of exiftool's
``-j -G`` output.

The parser is *self-identifying*: it binds tag values to paths via the
``SourceFile`` field in each JSON record, not by line position. Positional
drift (the latent bug class that affected the prior ``-s3 -f`` line-based
parser) is structurally impossible here. These tests exercise the binding,
the JSON-blob extraction (with mixed-in stderr status messages), the
single-vs-multi-file invariance, the missing-tag absence convention, and the
graceful empty-result on malformed output.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

from galbum.exiftool import batch_read_processed, _parse_exiftool_json


# ---------------------------------------------------------------------------
# _parse_exiftool_json — JSON blob extraction
# ---------------------------------------------------------------------------

class TestParseExiftoolJson:
    def test_clean_json(self):
        out = '[{"SourceFile":"/tmp/a.jpg"}]'
        assert _parse_exiftool_json(out) == [{"SourceFile": "/tmp/a.jpg"}]

    def test_strips_status_message_prefix(self):
        # Real exiftool stay_open output: stderr-merged status appears before JSON.
        out = '    3 image files read\n[{"SourceFile":"/tmp/a"}]'
        assert _parse_exiftool_json(out) == [{"SourceFile": "/tmp/a"}]

    def test_strips_status_message_suffix(self):
        out = '[{"SourceFile":"/tmp/a"}]\n    1 image files read\n'
        assert _parse_exiftool_json(out) == [{"SourceFile": "/tmp/a"}]

    def test_strips_status_message_both_sides(self):
        out = '    Warning: foo\n[{"SourceFile":"/tmp/a"}]\n    1 image files read'
        assert _parse_exiftool_json(out) == [{"SourceFile": "/tmp/a"}]

    def test_empty_array(self):
        assert _parse_exiftool_json("[]") == []

    def test_no_brackets_returns_empty(self):
        assert _parse_exiftool_json("    error: nothing readable") == []

    def test_malformed_json_returns_empty(self):
        assert _parse_exiftool_json("[{malformed}]") == []

    def test_non_array_returns_empty(self):
        # exiftool always emits an array under -j; defend anyway.
        assert _parse_exiftool_json('{"SourceFile":"/tmp/a"}') == []


# ---------------------------------------------------------------------------
# batch_read_processed — end-to-end with mocked exiftool process
# ---------------------------------------------------------------------------

def _make_et(canned_output: str):
    """Stand-in ExiftoolProcess whose .execute() returns the given string."""
    et = MagicMock()
    et.execute.return_value = canned_output
    return et


def _canned(records: list, status: str = "    {n} image files read") -> str:
    """Build the exiftool stay_open wire format: status header + JSON body."""
    body = json.dumps(records)
    if status:
        return status.replace("{n}", str(len(records))) + "\n" + body
    return body


class TestBatchReadProcessed:
    def test_empty_input(self):
        et = _make_et("")
        processed, offsets, naive = batch_read_processed([], et)
        assert processed == set() and offsets == {} and naive == {}
        et.execute.assert_not_called()

    def test_two_files_self_identifying(self):
        # Tag presence per file: A is a Google-scanned JPEG with IPTC naive-local;
        # B is a HEIC with explicit OffsetTimeOriginal. Each record's SourceFile
        # binds tags to the correct path.
        a = Path("/tmp/a.jpg")
        b = Path("/tmp/b.heic")
        canned = _canned([
            {
                "SourceFile": "/tmp/a.jpg",
                "EXIF:DateTimeOriginal": "2024:09:24 13:33:20+00:00",
                "Composite:DigitalCreationDateTime": "2024:09:24 21:33:20",
            },
            {
                "SourceFile": "/tmp/b.heic",
                "EXIF:DateTimeOriginal": "2024:06:12 11:17:37+00:00",
                "EXIF:OffsetTimeOriginal": "+09:00",
            },
        ])
        et = _make_et(canned)
        processed, offsets, naive = batch_read_processed([a, b], et)

        assert processed == {a, b}, "both files have valid DateTimeOriginal"
        assert offsets == {b: "+09:00"}
        assert naive == {a: "2024:09:24 21:33:20"}

    def test_records_returned_in_different_order_still_match(self):
        # Critical property of self-identifying records: even if exiftool reordered
        # its output, each path still gets its own tags. The line-positional
        # parser would have catastrophically misassigned in this scenario.
        a = Path("/tmp/a.jpg")
        b = Path("/tmp/b.jpg")
        canned = _canned([
            {"SourceFile": "/tmp/b.jpg", "EXIF:OffsetTimeOriginal": "+09:00"},
            {"SourceFile": "/tmp/a.jpg", "Composite:DigitalCreationDateTime": "2024:01:01 12:00:00"},
        ])
        et = _make_et(canned)
        _, offsets, naive = batch_read_processed([a, b], et)
        assert offsets == {b: "+09:00"}, "offset must bind to b regardless of record order"
        assert naive == {a: "2024:01:01 12:00:00"}, "naive must bind to a regardless of record order"

    def test_single_file(self):
        # JSON output is structurally identical for any number of files —
        # no special-casing of single-file mode required.
        a = Path("/tmp/single.heic")
        canned = _canned([
            {
                "SourceFile": "/tmp/single.heic",
                "EXIF:DateTimeOriginal": "2024:06:12 11:17:37+00:00",
                "EXIF:OffsetTimeOriginal": "+09:00",
            },
        ])
        et = _make_et(canned)
        processed, offsets, naive = batch_read_processed([a], et)
        assert processed == {a}
        assert offsets == {a: "+09:00"}
        assert naive == {}

    def test_xmp_datetime_original_marks_processed(self):
        # Galbum writes XMP:DateTimeOriginal (not EXIF) for PNG/GIF/WebP. The
        # processed-check must see XMP, otherwise re-runs without --force would
        # re-process every PNG every time.
        a = Path("/tmp/a.png")
        canned = _canned([
            {"SourceFile": "/tmp/a.png", "XMP:DateTimeOriginal": "2021:01:01 09:00:00+09:00"},
        ])
        et = _make_et(canned)
        processed, _, _ = batch_read_processed([a], et)
        assert processed == {a}, "XMP:DateTimeOriginal must count as processed"

    def test_quicktime_create_date_marks_processed(self):
        # MP4/MOV files: QuickTime:CreateDate is what galbum writes.
        a = Path("/tmp/a.mov")
        canned = _canned([
            {"SourceFile": "/tmp/a.mov", "QuickTime:CreateDate": "2021:01:01 00:00:00"},
        ])
        et = _make_et(canned)
        processed, _, _ = batch_read_processed([a], et)
        assert processed == {a}

    def test_zeroed_datetime_not_processed(self):
        # The all-zeros sentinel is not a real timestamp; reject it.
        a = Path("/tmp/zero.jpg")
        canned = _canned([
            {"SourceFile": "/tmp/zero.jpg", "EXIF:DateTimeOriginal": "0000:00:00 00:00:00"},
        ])
        et = _make_et(canned)
        processed, _, _ = batch_read_processed([a], et)
        assert processed == set()

    def test_missing_tags_absent_in_json(self):
        # Under `-j` (no `-f`), missing tags are simply absent from the record
        # rather than emitted as "-". Defend against both spellings.
        a = Path("/tmp/empty.jpg")
        canned = _canned([{"SourceFile": "/tmp/empty.jpg"}])
        et = _make_et(canned)
        processed, offsets, naive = batch_read_processed([a], et)
        assert processed == set() and offsets == {} and naive == {}

    def test_unknown_paths_in_records_ignored(self):
        # If exiftool emits a record for a path we didn't ask about (shouldn't
        # happen in practice, but be defensive), it doesn't pollute our maps.
        a = Path("/tmp/a.jpg")
        canned = _canned([
            {"SourceFile": "/tmp/a.jpg", "EXIF:DateTimeOriginal": "2024:01:01 00:00:00"},
            {"SourceFile": "/tmp/ghost.jpg", "EXIF:OffsetTimeOriginal": "+05:00"},
        ])
        et = _make_et(canned)
        processed, offsets, _ = batch_read_processed([a], et)
        assert processed == {a}
        assert offsets == {}, "ghost record's offset must not appear"

    def test_paths_with_unicode_and_spaces(self):
        # Real album path: "D:/Downloads/Takeout/Google 相簿/大阪42/IMG_0022.HEIC"
        path = Path("D:/Downloads/Takeout/Google 相簿/大阪42/IMG_0022.HEIC")
        canned = _canned([
            {
                "SourceFile": "D:/Downloads/Takeout/Google 相簿/大阪42/IMG_0022.HEIC",
                "EXIF:DateTimeOriginal": "2024:06:12 11:17:37+00:00",
                "EXIF:OffsetTimeOriginal": "+09:00",
            },
        ])
        et = _make_et(canned)
        processed, offsets, _ = batch_read_processed([path], et)
        assert processed == {path}
        assert offsets == {path: "+09:00"}

    def test_malformed_output_returns_empty_safely(self):
        a = Path("/tmp/a.jpg")
        et = _make_et("    error: exiftool exploded\nnonsense")
        processed, offsets, naive = batch_read_processed([a], et)
        assert processed == set() and offsets == {} and naive == {}

    def test_stderr_text_appended_does_not_break_json(self):
        # Regression: ExiftoolProcess separates stderr from stdout, then
        # appends stderr text after stdout. The JSON parser slices on the
        # outermost [ ... ] so trailing stderr (warnings, status messages)
        # never reaches json.loads. Without stream separation, stderr would
        # interleave INTO the JSON for large outputs (>~64 KB), splicing
        # bytes mid-string and producing invalid JSON.
        a = Path("/tmp/a.jpg")
        canned = (
            '[{"SourceFile": "/tmp/a.jpg", "EXIF:DateTimeOriginal": "2024:01:01 00:00:00"}]'
            "\n    1 image files read"          # stderr appended
            "\nWarning: something else"          # extra stderr
        )
        et = _make_et(canned)
        processed, _, _ = batch_read_processed([a], et)
        assert processed == {a}, "trailing stderr must not break JSON parsing"

    def test_three_files_each_with_one_distinct_signal(self):
        # Stress: three files, each carrying exactly one of {processed, offset,
        # naive-local}. Verifies the binding stays correct as the record set grows.
        a, b, c = Path("/tmp/a"), Path("/tmp/b"), Path("/tmp/c")
        canned = _canned([
            {"SourceFile": "/tmp/a", "EXIF:DateTimeOriginal": "2020:01:01 00:00:00"},
            {"SourceFile": "/tmp/b", "EXIF:OffsetTimeOriginal": "+05:30"},
            {"SourceFile": "/tmp/c", "Composite:DigitalCreationDateTime": "2020:01:01 12:00:00"},
        ])
        et = _make_et(canned)
        processed, offsets, naive = batch_read_processed([a, b, c], et)
        assert processed == {a}
        assert offsets == {b: "+05:30"}
        assert naive == {c: "2020:01:01 12:00:00"}
