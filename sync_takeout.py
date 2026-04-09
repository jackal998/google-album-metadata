#!/usr/bin/env python3
"""
sync_takeout.py — Write Google Takeout JSON metadata back into media files.

Usage:
  python sync_takeout.py --test-only --dry-run   # preview test folder
  python sync_takeout.py --test-only              # apply to test folder
  python sync_takeout.py                          # process all albums
  python sync_takeout.py --folder "2024 June-July Japan (Nishi-Nihon)"
"""

import argparse
import json
import logging
import re
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    from timezonefinder import TimezoneFinder
    _TZ_FINDER = TimezoneFinder()
except ImportError:
    _TZ_FINDER = None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_ROOT = Path("D:/Downloads/Takeout/Google 相簿")
TEST_FOLDER_NAME = "測試"

MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".heic", ".png", ".gif", ".webp",
    ".tif", ".tiff", ".dng", ".cr2", ".nef", ".arw",
    ".mp4", ".mov", ".m4v", ".avi",
}

SKIP_FILENAMES = {"thumbs.db", "desktop.ini", "failed_inserting_exif.txt"}

# Chinese and English edited-photo suffixes to strip
EDITED_SUFFIXES = ["-已編輯", "(已編輯)", "-edited", "-Edit", "_edited", " edited"]

# Candidate photo extensions when looking up a video's companion image JSON
COMPANION_PHOTO_EXTS = [".HEIC", ".heic", ".JPG", ".jpg", ".JPEG", ".jpeg", ".PNG", ".png"]

# Duplicate number pattern:  "IMG_9556(1)"  ->  base="IMG_9556"  num=1
DUPE_RE = re.compile(r"^(.*)\((\d+)\)$")

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class MediaFile:
    path: Path
    base_stem: str          # stem with (N) stripped
    number: Optional[int]   # N from (N), or None
    suffix: str             # ".HEIC" (preserves original case)
    is_edited: bool
    clean_stem: str         # base_stem with edited suffix stripped


@dataclass
class ParsedMetadata:
    dt_str: str             # "YYYY:MM:DD HH:MM:SS+HH:MM" (local tz if GPS known, else UTC)
    gps: Optional[dict]     # raw geo dict, or None
    description: Optional[str]
    favorited: bool


@dataclass
class MatchResult:
    json_path: Path
    match_type: str         # exact | duplicate | live_photo | edited_fallback | title_match


@dataclass
class JsonIndex:
    by_exact: dict          # "IMG_9556.HEIC.json" -> Path
    by_title: dict          # json["title"] -> Path
    all_stems: dict         # "IMG_9556" -> [Path, ...]


# ---------------------------------------------------------------------------
# exiftool long-running process
# ---------------------------------------------------------------------------


class ExiftoolProcess:
    """Persistent exiftool process using -stay_open for batch performance."""

    def __init__(self):
        self.proc = subprocess.Popen(
            ["exiftool", "-stay_open", "True", "-@", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
        )

    def execute(self, args: list) -> str:
        """Send a list of args, return stdout (stderr merged) up to {ready} sentinel."""
        cmd = "\n".join(str(a) for a in args) + "\n-execute\n"
        self.proc.stdin.write(cmd)
        self.proc.stdin.flush()
        lines = []
        while True:
            line = self.proc.stdout.readline()
            if not line:
                break
            stripped = line.rstrip("\n")
            if stripped == "{ready}":
                break
            lines.append(stripped)
        return "\n".join(lines)

    def close(self):
        try:
            self.proc.stdin.write("-stay_open\nFalse\n")
            self.proc.stdin.flush()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ---------------------------------------------------------------------------
# Filename parsing
# ---------------------------------------------------------------------------


def parse_media_filename(path: Path) -> MediaFile:
    """Decompose a media filename into its parts for JSON matching."""
    stem = path.stem          # "IMG_9556(1)"
    suffix = path.suffix      # ".HEIC"

    m = DUPE_RE.match(stem)
    if m:
        base_stem = m.group(1)
        number = int(m.group(2))
    else:
        base_stem = stem
        number = None

    is_edited = False
    clean_stem = base_stem
    for es in EDITED_SUFFIXES:
        if base_stem.endswith(es):
            clean_stem = base_stem[: -len(es)]
            is_edited = True
            break

    return MediaFile(
        path=path,
        base_stem=base_stem,
        number=number,
        suffix=suffix,
        is_edited=is_edited,
        clean_stem=clean_stem,
    )


# ---------------------------------------------------------------------------
# JSON index
# ---------------------------------------------------------------------------


def _stem_of_json(name: str) -> str:
    """Strip .json suffix, then strip everything after the last real extension."""
    without_json = name[: -len(".json")]   # "IMG_9556.HEIC(1)"
    # Base stem: strip trailing (N) if present
    m = DUPE_RE.match(Path(without_json).stem)
    return m.group(1) if m else Path(without_json).stem


def build_json_index(json_files: list) -> JsonIndex:
    by_exact = {}
    by_title = {}
    all_stems = {}

    for jp in json_files:
        by_exact[jp.name] = jp

        # Parse title field for UUID / truncation matching
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
            title = data.get("title", "")
            if title:
                by_title[title] = jp
        except Exception:
            pass

        stem = _stem_of_json(jp.name)
        all_stems.setdefault(stem, []).append(jp)

    return JsonIndex(by_exact=by_exact, by_title=by_title, all_stems=all_stems)


# ---------------------------------------------------------------------------
# JSON matching (5-step algorithm)
# ---------------------------------------------------------------------------


def find_json(mf: MediaFile, index: JsonIndex) -> Optional[MatchResult]:
    """Return the best-matching JSON path for this media file, or None."""

    # Step 1: Exact match  IMG_9556.HEIC -> IMG_9556.HEIC.json
    candidate = mf.path.name + ".json"
    if candidate in index.by_exact:
        return MatchResult(index.by_exact[candidate], "exact")

    # Step 2: Duplicate number reordering  IMG_9556(1).HEIC -> IMG_9556.HEIC(1).json
    if mf.number is not None:
        candidate = f"{mf.base_stem}{mf.suffix}({mf.number}).json"
        if candidate in index.by_exact:
            return MatchResult(index.by_exact[candidate], "duplicate")

    # Step 3: Live photo video orphan  IMG_9556(1).MP4 -> IMG_9556.HEIC(1).json
    if mf.suffix.upper() in (".MP4", ".MOV", ".M4V"):
        for photo_ext in COMPANION_PHOTO_EXTS:
            if mf.number is not None:
                candidate = f"{mf.base_stem}{photo_ext}({mf.number}).json"
            else:
                candidate = f"{mf.base_stem}{photo_ext}.json"
            if candidate in index.by_exact:
                return MatchResult(index.by_exact[candidate], "live_photo")

    # Step 4: Edited photo fallback  IMG_3818-已編輯.HEIC -> IMG_3818.HEIC.json
    if mf.is_edited:
        candidate = f"{mf.clean_stem}{mf.suffix}.json"
        if candidate in index.by_exact:
            return MatchResult(index.by_exact[candidate], "edited_fallback")
        if mf.number is not None:
            candidate = f"{mf.clean_stem}{mf.suffix}({mf.number}).json"
            if candidate in index.by_exact:
                return MatchResult(index.by_exact[candidate], "edited_fallback")

    # Step 5: Title-field match (handles UUID truncation in both directions)
    # e.g. media = "9A42C069-...-0000.mov", title = "9A42C069-...-00001E98C62951D8.mov"
    media_name = mf.path.name
    if len(mf.path.stem) > 10:
        for title, jp in index.by_title.items():
            short = min(len(media_name), len(title))
            # Both must share at least 80% of the shorter string as a common prefix
            threshold = int(short * 0.8)
            if threshold > 0 and media_name[:threshold] == title[:threshold]:
                return MatchResult(jp, "title_match")

    return None


# ---------------------------------------------------------------------------
# Metadata parsing
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# File type detection (extension + magic bytes for mismatch cases)
# ---------------------------------------------------------------------------


def _magic_type(path: Path) -> Optional[str]:
    """Detect actual file type from magic bytes (first 12 bytes)."""
    try:
        header = path.read_bytes()[:12]
    except Exception:
        return None
    if header[:2] == b"\xff\xd8":
        return "jpeg"
    if header[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if header[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        brand = header[8:12].lower()
        if brand in (b"heic", b"heix", b"mif1", b"msf1", b"heim", b"heis"):
            return "heic"
        if brand in (b"mp41", b"mp42", b"isom", b"iso2", b"avc1", b"f4v ", b"m4v "):
            return "mp4"
        if brand in (b"qt  ",):
            return "mov"
    return None


_TYPE_TO_EXT = {
    "jpeg": ".jpg", "heic": ".heic", "raw": ".dng",
    "png": ".png", "gif": ".gif", "webp": ".webp",
    "mp4": ".mp4", "mov": ".mov",
}


def get_file_type(path: Path) -> tuple:
    """Return (file_type, actual_path) where actual_path may differ if the file
    has a mismatched extension that needs a temp rename before exiftool."""
    ext = path.suffix.lower()
    ext_type_map = {
        ".jpg": "jpeg", ".jpeg": "jpeg",
        ".heic": "heic",
        ".dng": "raw", ".cr2": "raw", ".nef": "raw", ".arw": "raw",
        ".tif": "raw", ".tiff": "raw",
        ".png": "png",
        ".gif": "gif",
        ".webp": "webp",
        ".mp4": "mp4", ".m4v": "mp4",
        ".mov": "mov",
    }
    declared = ext_type_map.get(ext, "skip")

    # For image/container formats that can be misnamed (e.g. JPEG saved as .HEIC),
    # verify with magic bytes and return the actual type.
    if declared in ("heic", "raw", "png", "gif", "webp"):
        actual = _magic_type(path)
        if actual and actual != declared:
            logging.debug("Magic-byte mismatch: %s declared=%s actual=%s", path.name, declared, actual)
            return actual, True   # (type, needs_rename)

    return declared, False


@contextmanager
def _effective_path(path: Path, needs_rename: bool, actual_type: str):
    """If needs_rename, temporarily rename path to a correct extension, yield new path,
    then rename back. Otherwise yield path unchanged."""
    if not needs_rename:
        yield path
        return
    ext = _TYPE_TO_EXT.get(actual_type, path.suffix)
    temp_path = path.parent / (path.name + f".__fix{ext}")
    path.rename(temp_path)
    try:
        yield temp_path
    finally:
        # Rename back regardless of success/failure; temp file holds updated content
        if temp_path.exists():
            temp_path.rename(path)


# ---------------------------------------------------------------------------
# exiftool argument builder
# ---------------------------------------------------------------------------


def build_exiftool_args(
    path: Path,
    metadata: ParsedMetadata,
    file_type: str,
    overwrite: bool = True,
    set_file_dates: bool = True,
) -> list:
    args = ["-n", "-m"]     # -n: numeric values; -m: ignore minor errors (e.g. DNG maker notes)
    if overwrite:
        args.append("-overwrite_original")
    if not set_file_dates:
        args.append("-P")   # preserve file modification date only when not setting dates

    dt = metadata.dt_str

    if file_type in ("jpeg", "heic", "raw"):
        if dt:
            args += [
                f"-DateTimeOriginal={dt}",
                f"-CreateDate={dt}",
                f"-ModifyDate={dt}",
            ]
        if metadata.gps:
            lat = metadata.gps["latitude"]
            lon = metadata.gps["longitude"]
            alt = metadata.gps.get("altitude", 0.0)
            args += [
                f"-GPSLatitude={abs(lat)}",
                f"-GPSLatitudeRef={'N' if lat >= 0 else 'S'}",
                f"-GPSLongitude={abs(lon)}",
                f"-GPSLongitudeRef={'E' if lon >= 0 else 'W'}",
                f"-GPSAltitude={abs(alt)}",
                f"-GPSAltitudeRef={'0' if alt >= 0 else '1'}",
            ]
        if metadata.description:
            args += [
                f"-ImageDescription={metadata.description}",
                f"-XMP:Description={metadata.description}",
            ]

    elif file_type in ("png", "gif", "webp"):
        if dt:
            args += [
                f"-XMP:DateTimeOriginal={dt}",
                f"-XMP:CreateDate={dt}",
            ]
        if metadata.gps:
            lat = metadata.gps["latitude"]
            lon = metadata.gps["longitude"]
            alt = metadata.gps.get("altitude", 0.0)
            args += [
                f"-XMP:GPSLatitude={abs(lat)}",
                f"-XMP:GPSLatitudeRef={'N' if lat >= 0 else 'S'}",
                f"-XMP:GPSLongitude={abs(lon)}",
                f"-XMP:GPSLongitudeRef={'E' if lon >= 0 else 'W'}",
                f"-XMP:GPSAltitude={abs(alt)}",
            ]
        if metadata.description:
            args.append(f"-XMP:Description={metadata.description}")

    elif file_type in ("mp4", "mov"):
        if dt:
            # QuickTime fields don't carry timezone — write UTC time literally
            dt_qt = dt[:19]   # "YYYY:MM:DD HH:MM:SS"
            for tag in [
                "QuickTime:CreateDate",
                "QuickTime:ModifyDate",
                "QuickTime:TrackCreateDate",
                "QuickTime:TrackModifyDate",
                "QuickTime:MediaCreateDate",
                "QuickTime:MediaModifyDate",
            ]:
                args.append(f"-{tag}={dt_qt}")
            # Apple Keys atom supports timezone offset
            args.append(f"-Keys:CreationDate={dt}")
            args.append(f"-XMP:DateTimeOriginal={dt}")
        if metadata.gps:
            lat = metadata.gps["latitude"]
            lon = metadata.gps["longitude"]
            alt = metadata.gps.get("altitude", 0.0)
            # QuickTime GPS: signed decimal degrees
            args.append(f"-GPSCoordinates={lat} {lon} {alt}")
            args.append(f"-XMP:GPSLatitude={abs(lat)}")
            args.append(f"-XMP:GPSLatitudeRef={'N' if lat >= 0 else 'S'}")
            args.append(f"-XMP:GPSLongitude={abs(lon)}")
            args.append(f"-XMP:GPSLongitudeRef={'E' if lon >= 0 else 'W'}")
        if metadata.description:
            args.append(f"-XMP:Description={metadata.description}")

    if metadata.favorited:
        args.append("-XMP:Rating=5")

    # Set OS-level file timestamps so Windows/macOS file browser shows shot time
    if set_file_dates and metadata.dt_str:
        args += [
            f"-FileModifyDate={metadata.dt_str}",
            f"-FileCreateDate={metadata.dt_str}",
        ]

    args.append(str(path))
    return args


# ---------------------------------------------------------------------------
# Already-processed detection (batch read)
# ---------------------------------------------------------------------------


def batch_read_processed(media_files: list, et: ExiftoolProcess) -> set:
    """Return set of paths that already have a valid DateTimeOriginal / CreateDate."""
    if not media_files:
        return set()

    args = ["-DateTimeOriginal", "-QuickTime:CreateDate", "-s3", "-f"]
    args += [str(p) for p in media_files]
    output = et.execute(args)

    processed = set()
    lines = output.splitlines()
    # exiftool -s3 outputs one value per tag per file; with -f it prints "-" for missing
    # We get 2 lines per file (DateTimeOriginal, QuickTime:CreateDate)
    for i, path in enumerate(media_files):
        offset = i * 2
        if offset + 1 >= len(lines):
            break
        dt_orig = lines[offset].strip()
        qt_date = lines[offset + 1].strip()
        valid = lambda v: v and v not in ("-", "0000:00:00 00:00:00")
        if valid(dt_orig) or valid(qt_date):
            processed.add(path)

    return processed


# ---------------------------------------------------------------------------
# Folder scanning
# ---------------------------------------------------------------------------


def load_retry_files(failures_path: Path) -> dict:
    """Read failures.txt and return {folder_path: {file_path, ...}} for targeted retry."""
    folder_map = {}
    if not failures_path.exists():
        logging.error("failures.txt not found at %s", failures_path)
        return folder_map
    for line in failures_path.read_text(encoding="utf-8").splitlines():
        p = Path(line.strip())
        if p.exists():
            folder_map.setdefault(p.parent, set()).add(p)
        else:
            logging.warning("Retry file not found on disk: %s", p)
    return folder_map


def scan_folder(folder: Path) -> tuple:
    """Return (media_files, json_files) for a folder (non-recursive)."""
    media_files = []
    json_files = []
    for f in sorted(folder.iterdir()):
        if not f.is_file():
            continue
        if f.name.lower() in SKIP_FILENAMES:
            continue
        if f.suffix.lower() == ".json":
            json_files.append(f)
        elif f.suffix.lower() in MEDIA_EXTENSIONS:
            media_files.append(f)
    return media_files, json_files


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------


def process_folder(folder: Path, args, et: ExiftoolProcess, log, orphan_list: list, fail_list: list,
                   files_filter: Optional[set] = None):
    log.info("Processing folder: %s%s", folder.name,
             f" ({len(files_filter)} files)" if files_filter else "")
    media_files, json_files = scan_folder(folder)

    # When retrying, restrict to only the specified files
    if files_filter:
        media_files = [f for f in media_files if f in files_filter]

    if not media_files:
        log.info("  No media files found, skipping.")
        return

    index = build_json_index(json_files)

    # --retry-failures always force-processes; otherwise respect --force flag
    if files_filter or args.force:
        processed_set = set()
    else:
        processed_set = batch_read_processed(media_files, et)

    written = skipped = orphaned = failed = 0

    for path in media_files:
        mf = parse_media_filename(path)
        match = find_json(mf, index)

        if match is None:
            log.warning("[ORPH]  %s — no JSON match found", path.name)
            orphan_list.append(str(path))
            orphaned += 1
            continue

        metadata = parse_metadata(match.json_path)
        if metadata is None:
            log.warning("[FAIL]  %s — could not parse %s", path.name, match.json_path.name)
            fail_list.append(str(path))
            failed += 1
            continue

        if not args.force and path in processed_set:
            log.debug("[SKIP]  %s — already has DateTimeOriginal", path.name)
            skipped += 1
            continue

        gps_str = ""
        if metadata.gps:
            gps_str = f" gps={metadata.gps['latitude']:.4f},{metadata.gps['longitude']:.4f}"
        ts_str = f" ts={metadata.dt_str}" if metadata.dt_str else ""

        if args.dry_run:
            tag = match.match_type.upper()[:4]
            log.info("[DRY:%s] %s <- %s [%s]%s%s",
                     tag, path.name, match.json_path.name, match.match_type, ts_str, gps_str)
            written += 1
            continue

        file_type, needs_rename = get_file_type(path)
        if file_type == "skip":
            log.debug("[SKIP]  %s — unsupported type", path.name)
            skipped += 1
            continue

        with _effective_path(path, needs_rename, file_type) as effective:
            et_args = build_exiftool_args(effective, metadata, file_type,
                                           overwrite=not args.backup,
                                           set_file_dates=not args.no_file_dates)
            output = et.execute(et_args)

        label_map = {
            "exact": "OK",
            "duplicate": "DUPE",
            "live_photo": "LIVE",
            "edited_fallback": "EDIT",
            "title_match": "TITL",
        }
        label = label_map.get(match.match_type, match.match_type.upper())

        if "error" in output.lower() or "warning" in output.lower():
            # exiftool still exits 0 for warnings; check for real errors
            if "0 image files updated" in output and "error" in output.lower():
                log.error("[FAIL]  %s — exiftool: %s", path.name, output.strip())
                fail_list.append(str(path))
                failed += 1
                continue

        log.info("[%s]  %s <- %s [%s]%s%s",
                 label, path.name, match.json_path.name, match.match_type, ts_str, gps_str)
        written += 1

    action = "previewed" if args.dry_run else "written"
    print(f"[{folder.name}] {written} {action}, {skipped} skipped, {orphaned} orphan, {failed} failed")
    log.info("Folder %s complete: %d %s, %d skipped, %d orphan, %d failed",
             folder.name, written, action, skipped, orphaned, failed)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args():
    p = argparse.ArgumentParser(
        description="Sync Google Takeout JSON metadata back into media files."
    )
    p.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                   help="Root album folder (default: %(default)s)")
    p.add_argument("--folder", action="append", dest="folders",
                   help="Process only this subfolder name (repeatable)")
    p.add_argument("--test-only", action="store_true",
                   help=f"Process only the {TEST_FOLDER_NAME!r} folder")
    p.add_argument("--dry-run", action="store_true",
                   help="Preview operations without writing")
    p.add_argument("--force", action="store_true",
                   help="Re-process files that already have DateTimeOriginal")
    p.add_argument("--backup", action="store_true",
                   help="Keep exiftool _original backups (omits -overwrite_original)")
    p.add_argument("--no-file-dates", action="store_true", dest="no_file_dates",
                   help="Do NOT update OS file creation/modification dates (default: dates are set)")
    p.add_argument("--exclude", action="append", dest="excludes", metavar="NAME",
                   help="Skip this subfolder name (repeatable)")
    p.add_argument("--retry-failures", action="store_true", dest="retry_failures",
                   help="Re-process only files listed in failures.txt (targeted retry, no full scan)")
    p.add_argument("--log", type=Path, default=Path("sync_takeout.log"),
                   help="Log file path (default: %(default)s)")
    return p.parse_args()


def setup_logging(log_path: Path):
    fmt = "%(asctime)s %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    logging.basicConfig(
        level=logging.DEBUG,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    # Reduce console noise — only INFO+ to stdout
    logging.getLogger().handlers[1].setLevel(logging.INFO)


def check_exiftool() -> bool:
    if _TZ_FINDER:
        logging.info("timezonefinder active — timestamps will use local timezone from GPS")
    else:
        logging.info("timezonefinder not installed — timestamps will use UTC "
                     "(run: pip install timezonefinder to enable local timezone)")
    try:
        result = subprocess.run(["exiftool", "-ver"], capture_output=True, text=True)
        ver = result.stdout.strip()
        logging.info("exiftool version: %s", ver)
        return True
    except FileNotFoundError:
        print("ERROR: exiftool not found on PATH.")
        print("Install from https://exiftool.org/ and ensure it is in your PATH.")
        return False


def get_album_folders(root: Path, args) -> list:
    excludes = set(args.excludes or [])
    if args.test_only:
        return [root / TEST_FOLDER_NAME]
    if args.folders:
        return [root / name for name in args.folders if name not in excludes]
    return sorted(f for f in root.iterdir() if f.is_dir() and f.name not in excludes)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    args = parse_args()
    setup_logging(args.log)

    logging.info("=" * 60)
    logging.info("sync_takeout starting. root=%s dry_run=%s force=%s",
                 args.root, args.dry_run, args.force)

    if not check_exiftool():
        sys.exit(1)

    script_dir = Path(__file__).parent
    orphan_list = []
    fail_list = []

    with ExiftoolProcess() as et:
        if args.retry_failures:
            retry_map = load_retry_files(script_dir / "failures.txt")
            if not retry_map:
                logging.info("No retryable files found. Exiting.")
                return
            logging.info("Retrying %d file(s) across %d folder(s)",
                         sum(len(v) for v in retry_map.values()), len(retry_map))
            for folder, file_set in sorted(retry_map.items()):
                process_folder(folder, args, et, logging.getLogger(), orphan_list, fail_list,
                               files_filter=file_set)
        else:
            folders = get_album_folders(args.root, args)
            missing = [f for f in folders if not f.exists()]
            if missing:
                for f in missing:
                    logging.error("Folder not found: %s", f)
                sys.exit(1)
            for folder in folders:
                process_folder(folder, args, et, logging.getLogger(), orphan_list, fail_list)

    # Write summary files next to the script
    if orphan_list:
        orphan_path = script_dir / "orphans.txt"
        orphan_path.write_text("\n".join(orphan_list) + "\n", encoding="utf-8")
        logging.info("Orphan list written to: %s (%d files)", orphan_path, len(orphan_list))

    if fail_list:
        fail_path = script_dir / "failures.txt"
        fail_path.write_text("\n".join(fail_list) + "\n", encoding="utf-8")
        logging.info("Failure list written to: %s (%d files)", fail_path, len(fail_list))

    logging.info("Done.")


if __name__ == "__main__":
    main()
