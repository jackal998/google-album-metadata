import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import ParsedMetadata

try:
    from timezonefinder import TimezoneFinder
    _TZ_FINDER = TimezoneFinder()
except ImportError:
    _TZ_FINDER = None


def is_valid_gps(geo: dict) -> bool:
    """Return True only if geo contains real (non-zero) coordinates."""
    return geo is not None and not (
        geo.get("latitude", 0.0) == 0.0 and geo.get("longitude", 0.0) == 0.0
    )


def _parse_exif_offset(offset: str) -> Optional[timezone]:
    """Parse an EXIF OffsetTimeOriginal string like "+09:00" or "-05:00"."""
    try:
        sign = 1 if offset[0] == "+" else -1 if offset[0] == "-" else None
        if sign is None:
            return None
        hh, mm = offset[1:].split(":")
        return timezone(sign * timedelta(hours=int(hh), minutes=int(mm)))
    except (ValueError, IndexError):
        return None


def _infer_offset_from_naive(unix_ts: int, naive: str) -> Optional[timezone]:
    """Infer UTC offset by comparing a naive-local datetime string against unix_ts.

    Used when GPS and OffsetTimeOriginal are both absent but the file has a
    naive local timestamp from a non-EXIF source (e.g. IPTC DigitalCreationDateTime
    written by GooglePhotoScan and similar tools that don't record an offset).

    Returns None unless the implied offset is real-world plausible:
      - within ±14:00 (max real timezone span)
      - aligned to 15 minutes (every IANA timezone is)
    These rejection rules guard against junk EXIF, drifted clocks, or naive
    strings that semantically represent something other than the UTC instant
    (e.g. an analog photo's original capture date stored as DateCreated).
    """
    try:
        dt_local = datetime.strptime(naive, "%Y:%m:%d %H:%M:%S")
    except (ValueError, TypeError):
        return None
    dt_utc_naive = datetime.fromtimestamp(unix_ts, tz=timezone.utc).replace(tzinfo=None)
    diff = dt_local - dt_utc_naive
    total_seconds = int(diff.total_seconds())
    if abs(total_seconds) > 14 * 3600:
        return None
    if total_seconds % (15 * 60) != 0:
        return None
    return timezone(timedelta(seconds=total_seconds))


def _local_datetime(unix_ts: int, lat: Optional[float], lon: Optional[float],
                    existing_offset: Optional[str] = None,
                    existing_local_naive: Optional[str] = None) -> str:
    """Return EXIF-formatted datetime in local timezone.

    Resolution order:
      1. GPS coords → TimezoneFinder (most accurate, handles DST)
      2. existing_offset → fixed offset preserved from the media file's own EXIF
         OffsetTimeOriginal tag (recovers iPhone's recorded offset when Google
         strips GPS)
      3. existing_local_naive → infer offset by diffing IPTC's naive local
         timestamp against the JSON UTC unix_ts (recovers offset for sources
         like GooglePhotoScan that write IPTC DigitalCreationDateTime without
         an explicit offset tag)
      4. UTC fallback
    """
    dt_utc = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
    if _TZ_FINDER and lat is not None and lon is not None:
        try:
            tz_name = _TZ_FINDER.timezone_at(lat=lat, lng=lon)
            if tz_name is None:
                # timezone_at() returns None for points right on coastal/boundary edges;
                # fall back to closest_timezone_at() which always returns a result.
                tz_name = _TZ_FINDER.closest_timezone_at(lat=lat, lng=lon)
                if tz_name:
                    logging.debug(
                        "timezone_at returned None for (%.4f, %.4f); "
                        "using closest: %s", lat, lon, tz_name
                    )
            if tz_name:
                dt_local = dt_utc.astimezone(ZoneInfo(tz_name))
                offset = dt_local.strftime("%z")           # "+0900"
                offset_fmt = offset[:3] + ":" + offset[3:]  # "+09:00"
                return dt_local.strftime("%Y:%m:%d %H:%M:%S") + offset_fmt
            else:
                logging.warning(
                    "Could not resolve timezone for GPS (%.4f, %.4f) — falling back to UTC",
                    lat, lon
                )
        except ZoneInfoNotFoundError as exc:
            logging.warning(
                "ZoneInfo lookup failed for GPS (%.4f, %.4f): %s — "
                "run: pip install tzdata   (required on Windows)",
                lat, lon, exc
            )
        except Exception as exc:
            logging.warning(
                "Timezone lookup error for GPS (%.4f, %.4f): %s — falling back to UTC",
                lat, lon, exc
            )
    if existing_offset:
        tz = _parse_exif_offset(existing_offset)
        if tz is not None:
            dt_local = dt_utc.astimezone(tz)
            offset = dt_local.strftime("%z")            # "+0900"
            offset_fmt = offset[:3] + ":" + offset[3:]   # "+09:00"
            return dt_local.strftime("%Y:%m:%d %H:%M:%S") + offset_fmt
    if existing_local_naive:
        tz = _infer_offset_from_naive(unix_ts, existing_local_naive)
        if tz is not None:
            dt_local = dt_utc.astimezone(tz)
            offset = dt_local.strftime("%z")
            offset_fmt = offset[:3] + ":" + offset[3:]
            return dt_local.strftime("%Y:%m:%d %H:%M:%S") + offset_fmt
    return dt_utc.strftime("%Y:%m:%d %H:%M:%S+00:00")


def parse_metadata(json_path: Path,
                   existing_offset: Optional[str] = None,
                   existing_local_naive: Optional[str] = None,
                   ) -> Optional[ParsedMetadata]:
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logging.warning("Could not parse %s: %s", json_path.name, exc)
        return None

    # GPS: prefer geoDataExif, fall back to geoData (needed before timestamp for tz lookup)
    geo_exif = data.get("geoDataExif")
    geo_data = data.get("geoData")
    gps = None
    for geo in (geo_exif, geo_data):
        if is_valid_gps(geo):
            gps = geo
            break

    # Timestamp: prefer photoTakenTime, fall back to creationTime
    # Use GPS coords for local timezone lookup when available
    ts_block = data.get("photoTakenTime") or data.get("creationTime")
    dt_str = None
    if ts_block and ts_block.get("timestamp"):
        try:
            unix = int(ts_block["timestamp"])
            lat = gps["latitude"] if gps else None
            lon = gps["longitude"] if gps else None
            dt_str = _local_datetime(unix, lat, lon, existing_offset, existing_local_naive)
        except (ValueError, OSError):
            pass

    description = data.get("description", "").strip() or None
    favorited = bool(data.get("favorited", False))

    return ParsedMetadata(dt_str=dt_str, gps=gps, description=description, favorited=favorited)