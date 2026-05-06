import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .models import ParsedMetadata


def _to_utc_str(dt_str: str) -> str:
    """Convert "YYYY:MM:DD HH:MM:SS+HH:MM" to UTC "YYYY:MM:DD HH:MM:SS" (no offset).

    QuickTime date fields (CreateDate, ModifyDate, etc.) must be stored as UTC with
    no timezone indicator — that is the QuickTime/MP4 spec.  Feeding local time into
    those fields causes players and OS date pickers (including Windows Explorer) to
    double-shift the time by applying the local UTC offset a second time.
    """
    # EXIF uses colons in the date part; convert to ISO for fromisoformat()
    iso = dt_str[:10].replace(":", "-") + "T" + dt_str[11:]
    dt = datetime.fromisoformat(iso)
    return dt.astimezone(timezone.utc).strftime("%Y:%m:%d %H:%M:%S")


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
            # XMP encodes direction in the sign of the decimal — no Ref tags.
            args += [
                f"-XMP:GPSLatitude={lat}",
                f"-XMP:GPSLongitude={lon}",
                f"-XMP:GPSAltitude={alt}",
            ]
        if metadata.description:
            args.append(f"-XMP:Description={metadata.description}")

    elif file_type in ("mp4", "mov"):
        if dt:
            # QuickTime spec: these fields are UTC with no timezone marker.
            # Convert local time → UTC so players/OS don't double-shift the offset.
            dt_utc = _to_utc_str(dt)
            for tag in [
                "QuickTime:CreateDate",
                "QuickTime:ModifyDate",
                "QuickTime:TrackCreateDate",
                "QuickTime:TrackModifyDate",
                "QuickTime:MediaCreateDate",
                "QuickTime:MediaModifyDate",
            ]:
                args.append(f"-{tag}={dt_utc}")
            # Apple Keys atom and XMP support full timezone offset — use local time.
            args.append(f"-Keys:CreationDate={dt}")
            args.append(f"-XMP:DateTimeOriginal={dt}")
            args.append(f"-XMP:CreateDate={dt}")
        if metadata.gps:
            lat = metadata.gps["latitude"]
            lon = metadata.gps["longitude"]
            alt = metadata.gps.get("altitude", 0.0)
            # QuickTime GPS: signed decimal degrees
            args.append(f"-GPSCoordinates={lat} {lon} {alt}")
            # XMP encodes direction in the sign of the decimal — no Ref tags.
            args.append(f"-XMP:GPSLatitude={lat}")
            args.append(f"-XMP:GPSLongitude={lon}")
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


_BATCH_READ_TAGS = (
    # `-DateTimeOriginal` (no group qualifier) returns BOTH EXIF and XMP variants
    # under `-G`. PNG/GIF/WebP carry the date in XMP since galbum does not write
    # EXIF for those formats; JPEG/HEIC/RAW carry it in EXIF. Asking unqualified
    # gives us both keys in the JSON when both groups have a value.
    "DateTimeOriginal",
    "QuickTime:CreateDate",
    "OffsetTimeOriginal",
    "Composite:DigitalCreationDateTime",
)

# JSON-output keys under `-j -G` (group-0 prefix).
# Centralising the key strings prevents a typo from silently dropping a signal.
_KEYS_PROCESSED = (
    "EXIF:DateTimeOriginal",
    "XMP:DateTimeOriginal",
    "QuickTime:CreateDate",
)
_KEY_OFFSET_TIME_ORIGINAL = "EXIF:OffsetTimeOriginal"
_KEY_DIGITAL_CREATION_DT = "Composite:DigitalCreationDateTime"


def _parse_exiftool_json(output: str) -> list:
    """Extract the JSON array from a `-j -G` exiftool invocation.

    `ExiftoolProcess` merges stderr into stdout, so exiftool's status messages
    (e.g. ``    3 image files read``) appear interleaved with the JSON. Slice
    by the outermost ``[ ... ]`` rather than parsing the raw output, and fall
    back to an empty list on any malformation.
    """
    start = output.find("[")
    end = output.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(output[start:end + 1])
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def batch_read_processed(media_files: list,
                         et: ExiftoolProcess) -> tuple[set, dict, dict]:
    """Single batched read for processing-time decisions and timezone recovery.

    Uses exiftool's ``-j -G`` JSON output: each record is self-identifying via
    its ``SourceFile`` field, so positional misalignment is structurally
    impossible. (An earlier ``-s3 -f`` line-positional parser had a latent
    multi-file drift bug — JSON eliminates the entire bug class.)

    Returns (processed_set, offset_map, naive_local_map). All three signals
    are extracted from one exiftool invocation.

      processed_set    — files that already carry DateTimeOriginal/QT:CreateDate
      offset_map       — file → OffsetTimeOriginal (e.g. "+09:00") for tier-2 recovery
      naive_local_map  — file → IPTC DigitalCreationDateTime (naive local string)
                          for tier-3 offset inference. We deliberately use IPTC
                          (not EXIF) because galbum never writes IPTC, so this
                          signal survives across re-runs even after we stamp
                          DateTimeOriginal.
    """
    if not media_files:
        return set(), {}, {}

    args = ["-j", "-G"] + [f"-{t}" for t in _BATCH_READ_TAGS]
    args += [str(p) for p in media_files]
    output = et.execute(args)
    records = _parse_exiftool_json(output)

    # Bind records to their input Path by SourceFile. pathlib normalises
    # forward/back slashes on Windows so dict equality holds regardless of
    # which separator exiftool emitted.
    by_path: dict = {}
    for rec in records:
        src = rec.get("SourceFile")
        if isinstance(src, str):
            by_path[Path(src)] = rec

    processed: set = set()
    offsets: dict = {}
    naive_locals: dict = {}
    valid = lambda v: isinstance(v, str) and v and v != "0000:00:00 00:00:00"

    for path in media_files:
        rec = by_path.get(Path(str(path)))
        if rec is None:
            continue

        if any(valid(rec.get(k)) for k in _KEYS_PROCESSED):
            processed.add(path)
        offset = rec.get(_KEY_OFFSET_TIME_ORIGINAL)
        if valid(offset):
            offsets[path] = offset
        naive = rec.get(_KEY_DIGITAL_CREATION_DT)
        if valid(naive):
            naive_locals[path] = naive

    return processed, offsets, naive_locals
