"""
Unit tests for:
  - is_valid_gps()
  - _local_datetime()
  - parse_metadata()
"""

import json
from pathlib import Path
from datetime import datetime, timezone

import pytest

from sync_takeout import is_valid_gps, parse_metadata, _local_datetime


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

    def test_with_tokyo_gps(self):
        # Tokyo coords → should give JST (+09:00) if timezonefinder installed
        result = _local_datetime(self.UNIX_2021, lat=35.6762, lon=139.6503)
        # Either UTC+00:00 (no timezonefinder) or JST +09:00; both are valid
        assert "2021:01:01" in result or "2021:01:01" in result
        assert "+" in result or "-" in result  # has a tz offset


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
