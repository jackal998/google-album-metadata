"""
Unit tests for:
  - is_valid_gps()
  - _local_datetime()
  - parse_metadata()
"""

import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

from galbum import is_valid_gps, parse_metadata, _local_datetime
from galbum.metadata_parser import _infer_offset_from_naive


# ---------------------------------------------------------------------------
# is_valid_gps
# ---------------------------------------------------------------------------

class TestIsValidGps:
    def test_valid_coords(self):
        geo = {"latitude": 25.0619, "longitude": 121.545, "altitude": 0.0}
        assert is_valid_gps(geo) is True

    def test_zero_zero_is_invalid(self):
        geo = {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0}
        assert is_valid_gps(geo) is False

    def test_none_is_invalid(self):
        assert is_valid_gps(None) is False

    def test_zero_lat_nonzero_lon(self):
        geo = {"latitude": 0.0, "longitude": 121.5, "altitude": 0.0}
        assert is_valid_gps(geo) is True

    def test_negative_coords(self):
        geo = {"latitude": -33.868, "longitude": 151.209, "altitude": 5.0}
        assert is_valid_gps(geo) is True


# ---------------------------------------------------------------------------
# _local_datetime
# ---------------------------------------------------------------------------

class TestLocalDatetime:
    UNIX_2021 = 1609459200  # 2021-01-01 00:00:00 UTC

    def test_utc_fallback_when_no_tz_finder(self):
        # Without GPS coords (or when timezonefinder is absent), returns UTC
        result = _local_datetime(self.UNIX_2021, None, None)
        assert result.startswith("2021:01:01 00:00:00")
        assert "+00:00" in result

    def test_format_structure(self):
        result = _local_datetime(self.UNIX_2021, None, None)
        # Must be "YYYY:MM:DD HH:MM:SS+HH:MM"
        assert len(result) == 25
        assert result[4] == ":" and result[7] == ":"
        assert result[13] == ":" and result[16] == ":"

    def test_existing_offset_recovers_local_time_when_no_gps(self):
        # 2024-06-12 11:17:37 UTC + recorded +09:00 → 20:17:37 JST.
        # Mirrors the Google-Takeout case where geoData is zeroed but the file's
        # OffsetTimeOriginal still holds the camera-recorded offset.
        unix = 1718191057
        result = _local_datetime(unix, None, None, existing_offset="+09:00")
        assert result == "2024:06:12 20:17:37+09:00"

    def test_existing_offset_negative(self):
        unix = 1609459200  # 2021-01-01 00:00:00 UTC
        result = _local_datetime(unix, None, None, existing_offset="-05:00")
        assert result == "2020:12:31 19:00:00-05:00"

    def test_malformed_existing_offset_falls_back_to_utc(self):
        result = _local_datetime(self.UNIX_2021, None, None, existing_offset="garbage")
        assert result == "2021:01:01 00:00:00+00:00"

    # Tier 3: infer offset from naive-local IPTC timestamp ------------------

    def test_naive_local_infers_taipei_offset(self):
        # The GooglePhotoScan case: JSON UTC 13:33:20, IPTC 21:33:20 (Taipei).
        # Diff = +8h → infer +08:00 → write 21:33:20+08:00.
        unix = 1727184800   # 2024-09-24 13:33:20 UTC
        result = _local_datetime(unix, None, None,
                                 existing_local_naive="2024:09:24 21:33:20")
        assert result == "2024:09:24 21:33:20+08:00"

    def test_naive_local_infers_negative_offset(self):
        unix = 1609459200   # 2021-01-01 00:00:00 UTC
        # naive 19:00 of previous day → -05:00 (Eastern Standard)
        result = _local_datetime(unix, None, None,
                                 existing_local_naive="2020:12:31 19:00:00")
        assert result == "2020:12:31 19:00:00-05:00"

    def test_naive_local_rejects_diff_beyond_14_hours(self):
        # 16-hour diff is not a real-world timezone — fall through to UTC.
        unix = 1609459200   # 2021-01-01 00:00:00 UTC
        result = _local_datetime(unix, None, None,
                                 existing_local_naive="2021:01:01 16:00:00")
        assert result == "2021:01:01 00:00:00+00:00"

    def test_naive_local_rejects_misaligned_diff(self):
        # 7-minute diff is not aligned to 15-min — reject.
        unix = 1609459200
        result = _local_datetime(unix, None, None,
                                 existing_local_naive="2021:01:01 00:07:00")
        assert result == "2021:01:01 00:00:00+00:00"

    def test_naive_local_rejects_malformed(self):
        result = _local_datetime(self.UNIX_2021, None, None,
                                 existing_local_naive="not a datetime")
        assert result == "2021:01:01 00:00:00+00:00"

    def test_existing_offset_takes_priority_over_naive_local(self):
        # Both signals supplied; tier-2 (explicit offset) wins.
        unix = 1727184800
        result = _local_datetime(unix, None, None,
                                 existing_offset="+09:00",
                                 existing_local_naive="2024:09:24 21:33:20")
        # +09:00 → 22:33:20 JST (not 21:33:20 Taipei)
        assert result == "2024:09:24 22:33:20+09:00"

    def test_naive_local_idempotent_at_quarter_hour_offsets(self):
        # Nepal is +05:45 — the 15-minute alignment must not reject it.
        # Unix 1609459200 = 2021-01-01 00:00:00 UTC; +05:45 → 05:45:00.
        unix = 1609459200
        result = _local_datetime(unix, None, None,
                                 existing_local_naive="2021:01:01 05:45:00")
        assert result == "2021:01:01 05:45:00+05:45"

    def test_with_tokyo_gps(self):
        # Tokyo coords → JST (+09:00) if timezonefinder+tzdata installed, else UTC.
        # Either outcome is acceptable; what matters is that the result is a valid
        # EXIF datetime with an explicit timezone offset and the correct date.
        result = _local_datetime(self.UNIX_2021, lat=35.6762, lon=139.6503)
        # Date must be present (2021-01-01 in both UTC and JST for this timestamp)
        assert "2021:01:01" in result, f"Expected 2021:01:01 in result, got {result!r}"
        # Must have a timezone offset: "+HH:MM" or "-HH:MM"
        assert len(result) == 25, \
            f"Expected 'YYYY:MM:DD HH:MM:SS+HH:MM' (25 chars), got {result!r}"
        offset = result[19:]   # e.g. "+09:00" or "+00:00"
        assert offset[0] in ("+", "-"), \
            f"Timezone offset must start with + or -, got {offset!r}"
        # If timezonefinder + tzdata resolved the timezone, we expect JST
        if offset == "+09:00":
            assert result == "2021:01:01 09:00:00+09:00"
        else:
            # Fallback to UTC is also acceptable
            assert result == "2021:01:01 00:00:00+00:00"


# ---------------------------------------------------------------------------
# _infer_offset_from_naive (direct unit tests)
# ---------------------------------------------------------------------------

class TestInferOffsetFromNaive:
    def test_clean_taipei(self):
        tz = _infer_offset_from_naive(1727184800, "2024:09:24 21:33:20")
        assert tz is not None
        assert tz.utcoffset(None) == timedelta(hours=8)

    def test_zero_offset_is_real(self):
        # London winter — naive equals UTC. We accept this; downstream UTC
        # fallback would write the same value, so it's a no-op either way.
        tz = _infer_offset_from_naive(1609459200, "2021:01:01 00:00:00")
        assert tz is not None
        assert tz.utcoffset(None) == timedelta(0)

    def test_rejects_too_large(self):
        assert _infer_offset_from_naive(1609459200, "2021:01:02 12:00:00") is None

    def test_rejects_misaligned(self):
        # 1-second diff is not a timezone offset
        assert _infer_offset_from_naive(1609459200, "2021:01:01 00:00:01") is None

    def test_rejects_garbage(self):
        assert _infer_offset_from_naive(1609459200, "") is None
        assert _infer_offset_from_naive(1609459200, "garbage") is None
        assert _infer_offset_from_naive(1609459200, "2021-01-01 00:00:00") is None  # wrong sep


# ---------------------------------------------------------------------------
# parse_metadata
# ---------------------------------------------------------------------------

class TestParseMetadata:
    def _write_json(self, tmp_path, data: dict) -> Path:
        p = tmp_path / "meta.json"
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return p

    def test_full_metadata(self, tmp_path):
        data = {
            "title": "IMG_0006.PNG",
            "description": "a test photo",
            "photoTakenTime": {"timestamp": "1609459200"},
            "geoDataExif": {
                "latitude": 35.6762, "longitude": 139.6503,
                "altitude": 10.0, "latitudeSpan": 0.0, "longitudeSpan": 0.0
            },
            "geoData": {
                "latitude": 35.6762, "longitude": 139.6503,
                "altitude": 10.0, "latitudeSpan": 0.0, "longitudeSpan": 0.0
            },
            "favorited": True,
        }
        meta = parse_metadata(self._write_json(tmp_path, data))
        assert meta is not None
        assert "2021:01:01" in meta.dt_str
        assert meta.gps is not None
        assert meta.gps["latitude"] == pytest.approx(35.6762)
        assert meta.description == "a test photo"
        assert meta.favorited is True

    def test_prefers_photo_taken_time_over_creation_time(self, tmp_path):
        data = {
            "photoTakenTime": {"timestamp": "1609459200"},  # 2021-01-01
            "creationTime":   {"timestamp": "1000000000"},  # 2001-09-09
            "geoData": {"latitude": 0.0, "longitude": 0.0,
                         "altitude": 0.0, "latitudeSpan": 0.0, "longitudeSpan": 0.0},
        }
        meta = parse_metadata(self._write_json(tmp_path, data))
        assert "2021:01:01" in meta.dt_str

    def test_falls_back_to_creation_time(self, tmp_path):
        data = {
            "creationTime": {"timestamp": "1609459200"},
            "geoData": {"latitude": 0.0, "longitude": 0.0,
                         "altitude": 0.0, "latitudeSpan": 0.0, "longitudeSpan": 0.0},
        }
        meta = parse_metadata(self._write_json(tmp_path, data))
        assert "2021:01:01" in meta.dt_str

    def test_prefers_geo_data_exif_over_geo_data(self, tmp_path):
        data = {
            "photoTakenTime": {"timestamp": "1609459200"},
            "geoDataExif": {
                "latitude": 35.0, "longitude": 139.0,
                "altitude": 0.0, "latitudeSpan": 0.0, "longitudeSpan": 0.0
            },
            "geoData": {
                "latitude": 25.0, "longitude": 121.0,
                "altitude": 0.0, "latitudeSpan": 0.0, "longitudeSpan": 0.0
            },
        }
        meta = parse_metadata(self._write_json(tmp_path, data))
        # geoDataExif should win (lat=35 vs 25)
        assert meta.gps["latitude"] == pytest.approx(35.0)

    def test_falls_back_to_geo_data_when_exif_is_zero(self, tmp_path):
        data = {
            "photoTakenTime": {"timestamp": "1609459200"},
            "geoDataExif": {
                "latitude": 0.0, "longitude": 0.0,
                "altitude": 0.0, "latitudeSpan": 0.0, "longitudeSpan": 0.0
            },
            "geoData": {
                "latitude": 25.0, "longitude": 121.0,
                "altitude": 0.0, "latitudeSpan": 0.0, "longitudeSpan": 0.0
            },
        }
        meta = parse_metadata(self._write_json(tmp_path, data))
        assert meta.gps["latitude"] == pytest.approx(25.0)

    def test_no_gps_when_both_zero(self, tmp_path):
        data = {
            "photoTakenTime": {"timestamp": "1609459200"},
            "geoDataExif": {"latitude": 0.0, "longitude": 0.0,
                             "altitude": 0.0, "latitudeSpan": 0.0, "longitudeSpan": 0.0},
            "geoData":     {"latitude": 0.0, "longitude": 0.0,
                             "altitude": 0.0, "latitudeSpan": 0.0, "longitudeSpan": 0.0},
        }
        meta = parse_metadata(self._write_json(tmp_path, data))
        assert meta.gps is None

    def test_empty_description_becomes_none(self, tmp_path):
        data = {
            "description": "",
            "photoTakenTime": {"timestamp": "1609459200"},
        }
        meta = parse_metadata(self._write_json(tmp_path, data))
        assert meta.description is None

    def test_whitespace_description_becomes_none(self, tmp_path):
        data = {
            "description": "   ",
            "photoTakenTime": {"timestamp": "1609459200"},
        }
        meta = parse_metadata(self._write_json(tmp_path, data))
        assert meta.description is None

    def test_not_favorited_by_default(self, tmp_path):
        data = {"photoTakenTime": {"timestamp": "1609459200"}}
        meta = parse_metadata(self._write_json(tmp_path, data))
        assert meta.favorited is False

    def test_missing_timestamp_gives_none_dt(self, tmp_path):
        data = {"description": "no timestamp here"}
        meta = parse_metadata(self._write_json(tmp_path, data))
        assert meta is not None
        assert meta.dt_str is None

    def test_bad_json_returns_none(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not valid json", encoding="utf-8")
        assert parse_metadata(p) is None

    def test_missing_file_returns_none(self, tmp_path):
        assert parse_metadata(tmp_path / "nonexistent.json") is None
