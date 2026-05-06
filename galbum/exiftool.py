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


_TAGS_PER_FILE = (
    "DateTimeOriginal",
    "QuickTime:CreateDate",
    "OffsetTimeOriginal",
    "Composite:DigitalCreationDateTime",
)


def _strip_exiftool_metalines(output: str) -> list:
    """Drop exiftool's "======== <path>" file-separator headers and the
    trailing "    N image files read/updated" summary, leaving only tag values.

    With multiple files, exiftool emits a header line before each file's tag
    block. Without filtering, callers that index by `i * tags_per_file` read
    the header as data and silently misalign — a long-standing latent bug
    masked because most callers operated under --force which bypasses the
    consumer of this output.
    """
    out = []
    for line in output.splitlines():
        if line.startswith("======== "):
            continue
        stripped = line.strip()
        if stripped.endswith("image files read") or stripped.endswith("image files updated"):
            continue
        out.append(line)
    return out


def batch_read_processed(media_files: list,
                         et: ExiftoolProcess) -> tuple[set, dict, dict]:
    """Single batched read for processing-time decisions and timezone recovery.

    Returns (processed_set, offset_map, naive_local_map). All three signals
    are extracted from one exiftool invocation; adding tags to the args is
    cheaper than a second subprocess round-trip.

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

    args = [f"-{t}" for t in _TAGS_PER_FILE] + ["-s3", "-f"]
    args += [str(p) for p in media_files]
    output = et.execute(args)

    data_lines = _strip_exiftool_metalines(output)
    n = len(_TAGS_PER_FILE)

    processed: set = set()
    offsets: dict = {}
    naive_locals: dict = {}
    valid = lambda v: v and v not in ("-", "0000:00:00 00:00:00")

    for i, path in enumerate(media_files):
        base = i * n
        if base + n - 1 >= len(data_lines):
            break
        dt_orig = data_lines[base].strip()
        qt_date = data_lines[base + 1].strip()
        offset_tag = data_lines[base + 2].strip()
        naive_local = data_lines[base + 3].strip()

        if valid(dt_orig) or valid(qt_date):
            processed.add(path)
        if valid(offset_tag):
            offsets[path] = offset_tag
        if valid(naive_local):
            naive_locals[path] = naive_local

    return processed, offsets, naive_locals
