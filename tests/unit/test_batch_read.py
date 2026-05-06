"""
Unit tests for batch_read_processed() parser logic.

Critical: regression-tests the multi-file output parsing. Earlier versions
of this parser did not strip exiftool's "======== <path>" file-separator
headers, so reading N files with K tags each produced misaligned values
(e.g. file[1]'s OffsetTimeOriginal returning file[0]'s DateTimeOriginal).
"""

from pathlib import Path
from unittest.mock import MagicMock

from galbum.exiftool import batch_read_processed, _strip_exiftool_metalines


# ---------------------------------------------------------------------------
# _strip_exiftool_metalines
# ---------------------------------------------------------------------------

class TestStripMetalines:
    def test_strips_header_and_trailer(self):
        raw = (
            "======== /path/to/a.jpg\n"
            "2024:09:24 21:33:20\n"
            "-\n"
            "-\n"
            "2024:09:24 21:33:20\n"
            "======== /path/to/b.heic\n"
            "2024:06:12 11:17:37+00:00\n"
            "-\n"
            "+09:00\n"
            "-\n"
            "    2 image files read"
        )
        assert _strip_exiftool_metalines(raw) == [
            "2024:09:24 21:33:20", "-", "-", "2024:09:24 21:33:20",
            "2024:06:12 11:17:37+00:00", "-", "+09:00", "-",
        ]

    def test_strips_updated_trailer(self):
        raw = "value\n    1 image files updated"
        assert _strip_exiftool_metalines(raw) == ["value"]

    def test_handles_path_with_spaces_and_unicode(self):
        # Real-world path: "D:/Downloads/Takeout/Google 相簿/大阪42/IMG_0022.HEIC"
        raw = (
            "======== D:/Downloads/Takeout/Google 相簿/大阪42/IMG_0022.HEIC\n"
            "value\n"
            "    1 image files read"
        )
        assert _strip_exiftool_metalines(raw) == ["value"]


# ---------------------------------------------------------------------------
# batch_read_processed end-to-end (with mocked exiftool process)
# ---------------------------------------------------------------------------

def _make_et(canned_output: str):
    """Stand-in ExiftoolProcess whose .execute() returns the given string."""
    et = MagicMock()
    et.execute.return_value = canned_output
    return et


class TestBatchReadProcessed:
    def test_empty_input(self):
        et = _make_et("")
        processed, offsets, naive = batch_read_processed([], et)
        assert processed == set() and offsets == {} and naive == {}
        et.execute.assert_not_called()

    def test_two_files_correct_alignment(self):
        # Per-file tag order must be:
        #   DateTimeOriginal, QuickTime:CreateDate, OffsetTimeOriginal,
        #   Composite:DigitalCreationDateTime
        # File A: scanned JPEG (Google Takeout case) — UTC DateTimeOriginal,
        #   no offset, IPTC naive-local present.
        # File B: HEIC — UTC DateTimeOriginal, +09:00 offset, no IPTC.
        a = Path("/tmp/a.jpg")
        b = Path("/tmp/b.heic")
        canned = (
            "======== /tmp/a.jpg\n"
            "2024:09:24 13:33:20+00:00\n"
            "-\n"
            "-\n"
            "2024:09:24 21:33:20\n"
            "======== /tmp/b.heic\n"
            "2024:06:12 11:17:37+00:00\n"
            "-\n"
            "+09:00\n"
            "-\n"
            "    2 image files read"
        )
        et = _make_et(canned)
        processed, offsets, naive = batch_read_processed([a, b], et)

        assert processed == {a, b}, "both files have valid DateTimeOriginal"
        assert offsets == {b: "+09:00"}, \
            f"only HEIC has OffsetTimeOriginal; got {offsets!r}"
        assert naive == {a: "2024:09:24 21:33:20"}, \
            f"only JPEG has IPTC DigitalCreationDateTime; got {naive!r}"

    def test_single_file_no_header(self):
        # Single-file mode: exiftool stay_open omits "========" header.
        a = Path("/tmp/single.heic")
        canned = "2024:06:12 11:17:37+00:00\n-\n+09:00\n-"
        et = _make_et(canned)
        processed, offsets, naive = batch_read_processed([a], et)
        assert processed == {a}
        assert offsets == {a: "+09:00"}
        assert naive == {}

    def test_zeroed_datetime_not_processed(self):
        a = Path("/tmp/zero.jpg")
        canned = (
            "======== /tmp/zero.jpg\n"
            "0000:00:00 00:00:00\n"
            "-\n"
            "-\n"
            "-\n"
            "    1 image files read"
        )
        et = _make_et(canned)
        processed, _, _ = batch_read_processed([a], et)
        assert processed == set(), "0000 sentinel must not count as processed"

    def test_three_files_alignment(self):
        # Stress: 3 files, each with one signal in a different position.
        a, b, c = Path("/tmp/a"), Path("/tmp/b"), Path("/tmp/c")
        canned = (
            "======== /tmp/a\n"
            "2020:01:01 00:00:00\n-\n-\n-\n"
            "======== /tmp/b\n"
            "-\n-\n+05:30\n-\n"
            "======== /tmp/c\n"
            "-\n-\n-\n2020:01:01 12:00:00\n"
            "    3 image files read"
        )
        et = _make_et(canned)
        processed, offsets, naive = batch_read_processed([a, b, c], et)
        assert processed == {a}
        assert offsets == {b: "+05:30"}
        assert naive == {c: "2020:01:01 12:00:00"}
