import json
import logging
from datetime import datetime, timezone
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


def _local_datetime(unix_ts: int, lat: Optional[float], lon: Optional[float]) -> str:
    """Return EXIF-formatted datetime in local timezone (from GPS), else UTC."""
    dt_utc = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
    if _TZ_FINDER and lat is not None and lon is not None:
        try:
            tz_name = _TZ_FINDER.timezone_at(lat=lat, lng=lon)
            if tz_name:
                dt_local = dt_utc.astimezone(ZoneInfo(tz_name))
                offset = dt_local.strftime("%z")           # "+0900"
                offset_fmt = offset[:3] + ":" + offset[3:]  # "+09:00"
                return dt_local.strftime("%Y:%m:%d %H:%M:%S") + offset_fmt
        except (ZoneInfoNotFoundError, Exception):
            pass
    return dt_utc.strftime("%Y:%m:%d %H:%M:%S+00:00")


def parse_metadata(json_path: Path) -> Optional[ParsedMetadata]:
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
            dt_str = _local_datetime(unix, lat, lon)
        except (ValueError, OSError):
            pass

    description = data.get("description", "").strip() or None
    favorited = bool(data.get("favorited", False))

    return ParsedMetadata(dt_str=dt_str, gps=gps, description=description, favorited=favorited)
