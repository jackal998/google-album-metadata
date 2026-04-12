"""
Unit tests for build_exiftool_args().

Verifies that the correct ExifTool tag names and values are emitted for each
file type, metadata combination, and option flag.
"""

from pathlib import Path

import pytest

from galbum import ParsedMetadata, build_exiftool_args, _to_utc_str

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

FULL_META = ParsedMetadata(
    dt_str="2021:01:01 09:00:00+09:00",
    gps={"latitude": 35.6762, "longitude": 139.6503, "altitude": 10.0},
    description="test description",
    favorited=False,
)

NO_GPS_META = ParsedMetadata(
    dt_str="2021:01:01 00:00:00+00:00",
    gps=None,
    description=None,
    favorited=False,
)

FAVORITED_META = ParsedMetadata(
    dt_str="2021:01:01 00:00:00+00:00",
    gps=None,
    description=None,
    favorited=True,
)

FAKE_PATH = Path("/tmp/photo.heic")


def args_str(file_type: str, meta=FULL_META, **kwargs) -> list:
    """Shorthand: return args as joined strings for easy assertion."""
    return build_exiftool_args(FAKE_PATH, meta, file_type, **kwargs)


# ---------------------------------------------------------------------------
# Common flags
# ---------------------------------------------------------------------------

class TestCommonFlags:
    def test_numeric_flag_always_present(self):
        a = args_str("jpeg")
        assert "-n" in a

    def test_minor_errors_flag_always_present(self):
        a = args_str("jpeg")
        assert "-m" in a

    def test_overwrite_original_by_default(self):
        a = args_str("jpeg")
        assert "-overwrite_original" in a

    def test_no_overwrite_in_backup_mode(self):
        a = args_str("jpeg", overwrite=False)
        assert "-overwrite_original" not in a

    def test_path_is_last_argument(self):
        a = args_str("jpeg")
        assert a[-1] == str(FAKE_PATH)

    def test_file_modify_date_set_by_default(self):
        a = args_str("jpeg")
        assert any(arg.startswith("-FileModifyDate=") for arg in a)

    def test_no_file_dates_suppresses_file_timestamps(self):
        a = args_str("jpeg", set_file_dates=False)
        assert not any(arg.startswith("-FileModifyDate=") for arg in a)
        assert not any(arg.startswith("-FileCreateDate=") for arg in a)

    def test_preserve_flag_present_when_no_file_dates(self):
        a = args_str("jpeg", set_file_dates=False)
        assert "-P" in a

    def test_favorited_sets_rating_5(self):
        a = build_exiftool_args(FAKE_PATH, FAVORITED_META, "jpeg")
        assert "-XMP:Rating=5" in a

    def test_not_favorited_no_rating_tag(self):
        a = args_str("jpeg", meta=NO_GPS_META)
        assert "-XMP:Rating=5" not in a


# ---------------------------------------------------------------------------
# JPEG / HEIC / RAW  (EXIF tags)
# ---------------------------------------------------------------------------

class TestJpegHeicRaw:
    @pytest.mark.parametrize("file_type", ["jpeg", "heic", "raw"])
    def test_exif_datetime_tags(self, file_type):
        a = args_str(file_type)
        assert any(arg.startswith("-DateTimeOriginal=") for arg in a)
        assert any(arg.startswith("-CreateDate=") for arg in a)
        assert any(arg.startswith("-ModifyDate=") for arg in a)

    @pytest.mark.parametrize("file_type", ["jpeg", "heic", "raw"])
    def test_exif_gps_tags(self, file_type):
        a = args_str(file_type)
        assert any(arg.startswith("-GPSLatitude=") for arg in a)
        assert any(arg.startswith("-GPSLongitude=") for arg in a)
        assert any(arg.startswith("-GPSAltitude=") for arg in a)
        assert any(arg.startswith("-GPSLatitudeRef=") for arg in a)
        assert any(arg.startswith("-GPSLongitudeRef=") for arg in a)

    @pytest.mark.parametrize("file_type", ["jpeg", "heic", "raw"])
    def test_gps_ref_north(self, file_type):
        a = args_str(file_type)
        assert "-GPSLatitudeRef=N" in a
        assert "-GPSLongitudeRef=E" in a

    def test_gps_ref_south_west(self):
        meta = ParsedMetadata(
            dt_str="2021:01:01 00:00:00+00:00",
            gps={"latitude": -33.868, "longitude": -70.65, "altitude": 0.0},
            description=None, favorited=False,
        )
        a = build_exiftool_args(FAKE_PATH, meta, "jpeg")
        assert "-GPSLatitudeRef=S" in a
        assert "-GPSLongitudeRef=W" in a

    @pytest.mark.parametrize("file_type", ["jpeg", "heic", "raw"])
    def test_description_tags(self, file_type):
        a = args_str(file_type)
        assert any(arg.startswith("-ImageDescription=") for arg in a)
        assert any(arg.startswith("-XMP:Description=") for arg in a)

    @pytest.mark.parametrize("file_type", ["jpeg", "heic", "raw"])
    def test_no_gps_tags_when_gps_absent(self, file_type):
        a = args_str(file_type, meta=NO_GPS_META)
        assert not any(arg.startswith("-GPSLatitude=") for arg in a)

    @pytest.mark.parametrize("file_type", ["jpeg", "heic", "raw"])
    def test_no_datetime_tags_when_dt_absent(self, file_type):
        meta = ParsedMetadata(dt_str=None, gps=None, description=None, favorited=False)
        a = build_exiftool_args(FAKE_PATH, meta, file_type)
        assert not any(arg.startswith("-DateTimeOriginal=") for arg in a)


# ---------------------------------------------------------------------------
# PNG / GIF / WEBP  (XMP tags only)
# ---------------------------------------------------------------------------

class TestPngGifWebp:
    @pytest.mark.parametrize("file_type", ["png", "gif", "webp"])
    def test_uses_xmp_datetime(self, file_type):
        a = args_str(file_type)
        assert any(arg.startswith("-XMP:DateTimeOriginal=") for arg in a)
        # Must NOT use bare EXIF tags
        assert not any(arg.startswith("-DateTimeOriginal=") and "XMP" not in arg
                       for arg in a)

    @pytest.mark.parametrize("file_type", ["png", "gif", "webp"])
    def test_uses_xmp_gps(self, file_type):
        a = args_str(file_type)
        assert any(arg.startswith("-XMP:GPSLatitude=") for arg in a)
        assert any(arg.startswith("-XMP:GPSLongitude=") for arg in a)

    @pytest.mark.parametrize("file_type", ["png", "gif", "webp"])
    def test_no_xmp_gps_ref_tags(self, file_type):
        # XMP has no LatitudeRef/LongitudeRef — direction is encoded in the sign
        a = args_str(file_type)
        assert not any("GPSLatitudeRef" in arg for arg in a)
        assert not any("GPSLongitudeRef" in arg for arg in a)

    @pytest.mark.parametrize("file_type", ["png", "gif", "webp"])
    def test_xmp_gps_uses_signed_decimal(self, file_type):
        # North/East: positive values written as-is
        a = args_str(file_type)
        lat_arg = next(arg for arg in a if arg.startswith("-XMP:GPSLatitude="))
        lon_arg = next(arg for arg in a if arg.startswith("-XMP:GPSLongitude="))
        assert float(lat_arg.split("=")[1]) == pytest.approx(FULL_META.gps["latitude"])
        assert float(lon_arg.split("=")[1]) == pytest.approx(FULL_META.gps["longitude"])

    @pytest.mark.parametrize("file_type", ["png", "gif", "webp"])
    def test_xmp_gps_signed_decimal_south_west(self, file_type):
        meta = ParsedMetadata(
            dt_str="2021:01:01 00:00:00+00:00",
            gps={"latitude": -33.868, "longitude": -70.65, "altitude": 0.0},
            description=None, favorited=False,
        )
        a = build_exiftool_args(FAKE_PATH, meta, file_type)
        lat_arg = next(arg for arg in a if arg.startswith("-XMP:GPSLatitude="))
        lon_arg = next(arg for arg in a if arg.startswith("-XMP:GPSLongitude="))
        assert float(lat_arg.split("=")[1]) < 0, "South latitude should be negative"
        assert float(lon_arg.split("=")[1]) < 0, "West longitude should be negative"

    @pytest.mark.parametrize("file_type", ["png", "gif", "webp"])
    def test_uses_xmp_description(self, file_type):
        a = args_str(file_type)
        assert any(arg.startswith("-XMP:Description=") for arg in a)


# ---------------------------------------------------------------------------
# MP4 / MOV  (QuickTime tags)
# ---------------------------------------------------------------------------

class TestMp4Mov:
    @pytest.mark.parametrize("file_type", ["mp4", "mov"])
    def test_quicktime_create_date(self, file_type):
        a = args_str(file_type)
        assert any(arg.startswith("-QuickTime:CreateDate=") for arg in a)

    @pytest.mark.parametrize("file_type", ["mp4", "mov"])
    def test_quicktime_all_date_fields(self, file_type):
        a = args_str(file_type)
        qt_date_tags = [
            "QuickTime:CreateDate",
            "QuickTime:ModifyDate",
            "QuickTime:TrackCreateDate",
            "QuickTime:TrackModifyDate",
            "QuickTime:MediaCreateDate",
            "QuickTime:MediaModifyDate",
        ]
        for tag in qt_date_tags:
            assert any(arg.startswith(f"-{tag}=") for arg in a), \
                f"Missing tag -{tag}= for file_type={file_type!r}"

    @pytest.mark.parametrize("file_type", ["mp4", "mov"])
    def test_keys_creation_date_with_offset(self, file_type):
        a = args_str(file_type)
        assert any(arg.startswith("-Keys:CreationDate=") for arg in a)

    @pytest.mark.parametrize("file_type", ["mp4", "mov"])
    def test_keys_creation_date_preserves_offset(self, file_type):
        # Keys:CreationDate (Apple atom) supports full ISO 8601 with timezone offset.
        # FULL_META has +09:00 — the value written must preserve that offset,
        # unlike QuickTime fields which must be plain UTC.
        a = args_str(file_type)
        keys_vals = [arg.split("=", 1)[1] for arg in a
                     if arg.startswith("-Keys:CreationDate=")]
        assert keys_vals, "No Keys:CreationDate arg found"
        val = keys_vals[0]
        assert "+09:00" in val, \
            f"Keys:CreationDate should preserve +09:00 offset from input, got {val!r}"

    @pytest.mark.parametrize("file_type", ["mp4", "mov"])
    def test_xmp_datetime_original(self, file_type):
        a = args_str(file_type)
        assert any(arg.startswith("-XMP:DateTimeOriginal=") for arg in a)

    @pytest.mark.parametrize("file_type", ["mp4", "mov"])
    def test_xmp_create_date(self, file_type):
        # XMP:CreateDate added alongside DateTimeOriginal for video editors
        a = args_str(file_type)
        assert any(arg.startswith("-XMP:CreateDate=") for arg in a)

    @pytest.mark.parametrize("file_type", ["mp4", "mov"])
    def test_gps_coordinates(self, file_type):
        a = args_str(file_type)
        assert any(arg.startswith("-GPSCoordinates=") for arg in a)

    @pytest.mark.parametrize("file_type", ["mp4", "mov"])
    def test_no_xmp_gps_ref_tags(self, file_type):
        # XMP has no LatitudeRef/LongitudeRef — direction is encoded in the sign
        a = args_str(file_type)
        assert not any("XMP:GPSLatitudeRef" in arg for arg in a)
        assert not any("XMP:GPSLongitudeRef" in arg for arg in a)

    @pytest.mark.parametrize("file_type", ["mp4", "mov"])
    def test_xmp_gps_uses_signed_decimal(self, file_type):
        a = args_str(file_type)
        lat_arg = next(arg for arg in a if arg.startswith("-XMP:GPSLatitude="))
        lon_arg = next(arg for arg in a if arg.startswith("-XMP:GPSLongitude="))
        assert float(lat_arg.split("=")[1]) == pytest.approx(FULL_META.gps["latitude"])
        assert float(lon_arg.split("=")[1]) == pytest.approx(FULL_META.gps["longitude"])

    @pytest.mark.parametrize("file_type", ["mp4", "mov"])
    def test_quicktime_date_is_utc(self, file_type):
        # QuickTime date fields must be UTC with no timezone marker.
        # FULL_META has +09:00, so UTC value should be 00:00:00 (not 09:00:00).
        a = args_str(file_type)
        qt_vals = [arg.split("=", 1)[1] for arg in a
                   if arg.startswith("-QuickTime:CreateDate=")]
        assert qt_vals, "No QuickTime:CreateDate found"
        val = qt_vals[0]
        assert "+" not in val and val[1:].count("-") == 0, \
            f"QuickTime:CreateDate should have no tz offset, got {val!r}"
        assert "00:00:00" in val, \
            f"Expected UTC time 00:00:00 (converted from +09:00), got {val!r}"


# ---------------------------------------------------------------------------
# _to_utc_str helper
# ---------------------------------------------------------------------------

class TestToUtcStr:
    def test_positive_offset(self):
        # 09:00 JST → 00:00 UTC
        assert _to_utc_str("2021:01:01 09:00:00+09:00") == "2021:01:01 00:00:00"

    def test_utc_passthrough(self):
        assert _to_utc_str("2021:01:01 00:00:00+00:00") == "2021:01:01 00:00:00"

    def test_positive_offset_crosses_midnight(self):
        # 2021-01-01 01:00:00+08:00 → 2020-12-31 17:00:00 UTC
        assert _to_utc_str("2021:01:01 01:00:00+08:00") == "2020:12:31 17:00:00"

    def test_half_hour_offset(self):
        # India Standard Time +05:30
        assert _to_utc_str("2021:06:15 12:00:00+05:30") == "2021:06:15 06:30:00"
