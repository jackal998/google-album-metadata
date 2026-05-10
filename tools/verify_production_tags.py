"""Stratified-sample verification of galbum's production write output.

Walks a previously-galbum-synced Takeout extract, classifies each media file
by edge-case bucket (match-type, sidecar format, recovery-tier evidence),
draws a stratified random sample (default 15% of total, with at least one
file from every non-empty bucket), batch-reads relevant tags via exiftool,
compares against the JSON sidecar source-of-truth, and emits a markdown
report.

This script is read-only — it never writes EXIF, never moves files, never
modifies anything. Safe to run repeatedly.

Defaults match the May-2026 Takeout layout. Run from the repo root:

  python tools/verify_production_tags.py
  python tools/verify_production_tags.py --root D:/path --sample-pct 0.20
  python tools/verify_production_tags.py --limit 30           # smoke test
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# Allow `python tools/verify_production_tags.py` from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from galbum.exiftool import ExiftoolProcess  # noqa: E402
from galbum.filename_parser import parse_media_filename  # noqa: E402
from galbum.json_matching import build_json_index, find_json  # noqa: E402
from galbum.scanner import scan_folder  # noqa: E402

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_ROOT = Path(r"D:/Takeout-0508/Takeout/Google 相簿")
DEFAULT_SAMPLE_PCT = 0.15
EXIFTOOL_BATCH = 400  # files per exiftool call

# Tags read for verification. Group-prefixed under -G.
_TAGS = (
    "DateTimeOriginal",
    "OffsetTimeOriginal",
    "QuickTime:CreateDate",
    "Keys:CreationDate",
    "XMP:DateTimeOriginal",
    "Composite:DigitalCreationDateTime",
    "GPSLatitude",
    "GPSLongitude",
    "GPSCoordinates",
    "ImageDescription",
    "XMP:Description",
    "XMP:Rating",
)

_VIDEO_EXTS = {".mp4", ".mov", ".m4v"}
# Galbum writes XMP only (not EXIF) for these formats — see exiftool.py.
# So XMP:DateTimeOriginal is authoritative; any EXIF:DateTimeOriginal is stale
# pre-existing data we should ignore.
_XMP_AUTHORITATIVE_EXTS = {".png", ".gif", ".webp"}

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass
class FileRecord:
    media: Path
    sidecar: Optional[Path]
    match_type: str          # exact | duplicate | live_photo | edited_fallback | title_match | orphan
    sidecar_format: str      # legacy_json | new_full | new_truncated | new_dupe_inside
    json_data: Optional[dict] = None  # parsed sidecar JSON
    is_failed_video: bool = False     # under 失敗的影片/

    @property
    def is_video(self) -> bool:
        return self.media.suffix.lower() in _VIDEO_EXTS


@dataclass
class CheckResult:
    rec: FileRecord
    date_status: str         # PASS | FAIL | NA
    gps_status: str          # PASS | FAIL | NA
    desc_status: str         # PASS | FAIL | NA
    fav_status: str          # PASS | FAIL | NA
    # OTO consistency status — independent of date correctness:
    #   CONSISTENT — DTO offset matches OTO, or both absent
    #   STALE      — DTO embeds offset X, OTO has different value Y (timezone-shift risk)
    #   MISSING    — DTO embeds offset, OTO absent (cleaner if OTO matched)
    #   NAIVE      — DTO has no offset; relying on OTO alone (no inconsistency)
    #   NA         — couldn't evaluate (video, orphan, no DTO)
    oto_status: str = "NA"
    oto_dto_offset: Optional[str] = None
    oto_oto_value: Optional[str] = None
    notes: list = field(default_factory=list)
    actual: dict = field(default_factory=dict)  # raw tag values, for failure context


# ---------------------------------------------------------------------------
# Walk + match
# ---------------------------------------------------------------------------


def _classify_sidecar_format(sidecar_name: str) -> str:
    if ".supplemental-metadata.json" in sidecar_name or ".supplemental-metadat.json" in sidecar_name \
       or ".supplemental-metada.json" in sidecar_name or ".supplemental-metad.json" in sidecar_name \
       or ".supplemental-meta.json" in sidecar_name:
        if re.search(r"\.supplemental-meta(?:data|dat|da|d)?\(\d+\)\.json$", sidecar_name):
            return "new_dupe_inside"
        if ".supplemental-metadata.json" in sidecar_name:
            return "new_full"
        return "new_truncated"
    return "legacy_json"


def walk_and_match(root: Path) -> list[FileRecord]:
    """Walk root recursively, build per-folder json indexes, match each media."""
    records: list[FileRecord] = []
    for folder in sorted(p for p in root.rglob("*") if p.is_dir()):
        try:
            media_files, json_files = scan_folder(folder)
        except (OSError, PermissionError):
            continue
        if not media_files:
            continue
        index = build_json_index(json_files)
        is_failed_dir = folder.name == "失敗的影片"
        for mp in media_files:
            mf = parse_media_filename(mp)
            match = find_json(mf, index)
            if match is None:
                records.append(FileRecord(
                    media=mp, sidecar=None, match_type="orphan",
                    sidecar_format="none", is_failed_video=is_failed_dir,
                ))
                continue
            fmt = _classify_sidecar_format(match.json_path.name)
            try:
                data = json.loads(match.json_path.read_text(encoding="utf-8"))
            except Exception:
                data = None
            records.append(FileRecord(
                media=mp, sidecar=match.json_path,
                match_type=match.match_type, sidecar_format=fmt,
                json_data=data, is_failed_video=is_failed_dir,
            ))
    # Also pick up media in the root itself
    try:
        media_files, json_files = scan_folder(root)
    except (OSError, PermissionError):
        media_files, json_files = [], []
    if media_files:
        index = build_json_index(json_files)
        for mp in media_files:
            mf = parse_media_filename(mp)
            match = find_json(mf, index)
            if match is None:
                records.append(FileRecord(
                    media=mp, sidecar=None, match_type="orphan",
                    sidecar_format="none",
                ))
            else:
                fmt = _classify_sidecar_format(match.json_path.name)
                try:
                    data = json.loads(match.json_path.read_text(encoding="utf-8"))
                except Exception:
                    data = None
                records.append(FileRecord(
                    media=mp, sidecar=match.json_path,
                    match_type=match.match_type, sidecar_format=fmt,
                    json_data=data,
                ))
    return records


# ---------------------------------------------------------------------------
# Bucketing + sampling
# ---------------------------------------------------------------------------


def bucket_key(rec: FileRecord) -> tuple:
    """Return a tuple of bucket-defining attributes for stratification."""
    has_gps = False
    if rec.json_data:
        for geo_field in ("geoDataExif", "geoData"):
            geo = rec.json_data.get(geo_field) or {}
            if (geo.get("latitude") or 0.0) != 0.0 or (geo.get("longitude") or 0.0) != 0.0:
                has_gps = True
                break
    return (rec.match_type, rec.sidecar_format, "gps" if has_gps else "no_gps",
            "video" if rec.is_video else "photo",
            "failed" if rec.is_failed_video else "ok")


def stratified_sample(records: list[FileRecord], target_pct: float, seed: int,
                      limit: Optional[int]) -> list[FileRecord]:
    rng = random.Random(seed)
    by_bucket: dict[tuple, list[FileRecord]] = defaultdict(list)
    for r in records:
        by_bucket[bucket_key(r)].append(r)

    target = int(len(records) * target_pct) if limit is None else min(limit, len(records))
    sampled: list[FileRecord] = []
    seen: set[Path] = set()

    # Phase 1: at least one from each populated bucket
    for bucket, items in by_bucket.items():
        pick = rng.choice(items)
        if pick.media not in seen:
            sampled.append(pick)
            seen.add(pick.media)

    # Phase 2: fill remainder with proportional random sampling across all records
    remaining = [r for r in records if r.media not in seen]
    rng.shuffle(remaining)
    for r in remaining:
        if len(sampled) >= target:
            break
        sampled.append(r)
        seen.add(r.media)

    return sampled


# ---------------------------------------------------------------------------
# Tag reading + comparison
# ---------------------------------------------------------------------------


def batch_read_tags(paths: list[Path], et: ExiftoolProcess) -> dict[Path, dict]:
    if not paths:
        return {}
    out: dict[Path, dict] = {}
    for offset in range(0, len(paths), EXIFTOOL_BATCH):
        chunk = paths[offset: offset + EXIFTOOL_BATCH]
        args = ["-j", "-G", "-n"] + [f"-{t}" for t in _TAGS]
        args += [str(p) for p in chunk]
        raw = et.execute(args)
        # Slice the bracketed JSON; stderr may be appended.
        start, end = raw.find("["), raw.rfind("]")
        if start == -1 or end <= start:
            continue
        try:
            records = json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            continue
        for rec in records:
            src = rec.get("SourceFile")
            if isinstance(src, str):
                out[Path(src)] = rec
    return out


_DT_RE = re.compile(r"^(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})(.*)$")


def _has_offset(value: str) -> bool:
    """True if the date string carries its own offset/Z suffix."""
    m = _DT_RE.match(value.strip()) if isinstance(value, str) else None
    return bool(m and m.group(7).strip())


def parse_dt_tag(value: str) -> Optional[datetime]:
    """Parse an exiftool date string. Returns aware UTC datetime, or None."""
    if not isinstance(value, str) or not value:
        return None
    m = _DT_RE.match(value.strip())
    if not m:
        return None
    y, mo, d, h, mi, s, suffix = m.groups()
    try:
        naive = datetime(int(y), int(mo), int(d), int(h), int(mi), int(s))
    except ValueError:
        return None
    suffix = suffix.strip()
    if suffix.startswith("+") or suffix.startswith("-"):
        try:
            sign = 1 if suffix[0] == "+" else -1
            hh, mm = suffix[1:].split(":") if ":" in suffix[1:] else (suffix[1:3], suffix[3:5])
            tz = timezone(sign * timedelta(hours=int(hh), minutes=int(mm)))
            return naive.replace(tzinfo=tz).astimezone(timezone.utc)
        except (ValueError, IndexError):
            pass
    if suffix.upper() == "Z":
        return naive.replace(tzinfo=timezone.utc)
    # No suffix — caller decides whether to treat as UTC or local
    return naive.replace(tzinfo=timezone.utc)


def _resolve_photo_utc(dto: str, offset: Optional[str]) -> Optional[datetime]:
    """Resolve a photo's effective UTC instant from DTO and optional OTO.

    Priority:
      1. If DTO carries its own offset/Z suffix, trust it (this is what the most
         recent writer chose). OTO is informational at best.
      2. If DTO is naive and OTO is present, combine them.
      3. If DTO is naive and no OTO, treat DTO as UTC (galbum's tier-4 fallback).
    """
    if not dto:
        return None
    if _has_offset(dto):
        return parse_dt_tag(dto)
    if offset and isinstance(offset, str):
        return parse_dt_tag(f"{dto[:19]}{offset}")
    return parse_dt_tag(dto)


def compare_one(rec: FileRecord, actual: dict) -> CheckResult:
    res = CheckResult(rec=rec,
                      date_status="NA", gps_status="NA",
                      desc_status="NA", fav_status="NA",
                      actual=actual)

    if rec.is_failed_video:
        res.notes.append("File is in 失敗的影片/ — pre-flagged corrupt by Google; skipping checks.")
        return res

    if rec.sidecar is None or rec.json_data is None:
        res.notes.append("Orphan or unreadable sidecar; nothing to compare.")
        return res

    # ------- Date check
    ts_block = rec.json_data.get("photoTakenTime") or rec.json_data.get("creationTime")
    if ts_block and ts_block.get("timestamp"):
        try:
            expected_utc = datetime.fromtimestamp(int(ts_block["timestamp"]), tz=timezone.utc)
        except (ValueError, OSError):
            expected_utc = None
        if expected_utc is not None:
            # Pick the file's stored datetime. For videos: QuickTime:CreateDate is UTC by spec.
            # For photos: EXIF:DateTimeOriginal is naive but should be paired with EXIF:OffsetTimeOriginal.
            if rec.is_video:
                qt_str = actual.get("QuickTime:CreateDate") or actual.get("XMP:CreateDate")
                if qt_str:
                    got = parse_dt_tag(qt_str)
                    if got is not None and abs((got - expected_utc).total_seconds()) <= 2:
                        res.date_status = "PASS"
                    else:
                        res.date_status = "FAIL"
                        res.notes.append(
                            f"video datetime mismatch — expected {expected_utc} UTC, "
                            f"got QuickTime:CreateDate={qt_str}"
                        )
                else:
                    res.date_status = "FAIL"
                    res.notes.append("video has no QuickTime:CreateDate")
            else:
                # Photo: pick the authoritative tag for this format.
                #   PNG/GIF/WebP: galbum writes XMP only; EXIF (if present) is
                #     stale pre-galbum data — XMP:DateTimeOriginal is truth.
                #   JPEG/HEIC/RAW: galbum writes EXIF; EXIF:DateTimeOriginal
                #     is truth. XMP fallback only if EXIF is absent.
                if rec.media.suffix.lower() in _XMP_AUTHORITATIVE_EXTS:
                    dto = actual.get("XMP:DateTimeOriginal") or actual.get("EXIF:DateTimeOriginal")
                else:
                    dto = actual.get("EXIF:DateTimeOriginal") or actual.get("XMP:DateTimeOriginal")
                offset = actual.get("EXIF:OffsetTimeOriginal")

                # OTO consistency check (independent of date correctness)
                if rec.media.suffix.lower() not in _XMP_AUTHORITATIVE_EXTS and dto:
                    embedded = ""
                    m = _DT_RE.match(dto.strip())
                    if m:
                        embedded = m.group(7).strip()
                    res.oto_dto_offset = embedded or None
                    res.oto_oto_value = offset if isinstance(offset, str) else None
                    if embedded and offset and isinstance(offset, str):
                        res.oto_status = "CONSISTENT" if embedded == offset else "STALE"
                    elif embedded and not offset:
                        res.oto_status = "MISSING"
                    elif not embedded and offset:
                        res.oto_status = "NAIVE"
                    else:
                        res.oto_status = "CONSISTENT"  # both absent
                got = _resolve_photo_utc(dto, offset)
                if dto and got is not None and abs((got - expected_utc).total_seconds()) <= 2:
                    res.date_status = "PASS"
                    # Informational: flag OTO inconsistency without failing the date check.
                    if dto and _has_offset(dto) and offset and isinstance(offset, str):
                        m = _DT_RE.match(dto.strip())
                        embedded = m.group(7).strip() if m else ""
                        if embedded and embedded != offset:
                            res.notes.append(
                                f"OTO inconsistency (informational) — DTO embeds {embedded}, "
                                f"OffsetTimeOriginal is {offset} (likely stale from prior writer)"
                            )
                elif dto:
                    res.date_status = "FAIL"
                    res.notes.append(
                        f"photo datetime mismatch — expected {expected_utc} UTC, "
                        f"got DTO={dto} offset={offset}"
                    )
                else:
                    res.date_status = "FAIL"
                    res.notes.append("photo has no DateTimeOriginal")

    # ------- GPS check
    geo = None
    for fld in ("geoDataExif", "geoData"):
        g = rec.json_data.get(fld) or {}
        if (g.get("latitude") or 0.0) != 0.0 or (g.get("longitude") or 0.0) != 0.0:
            geo = g
            break
    if geo:
        exp_lat, exp_lon = float(geo["latitude"]), float(geo["longitude"])
        got_lat = actual.get("EXIF:GPSLatitude") or actual.get("XMP:GPSLatitude")
        got_lon = actual.get("EXIF:GPSLongitude") or actual.get("XMP:GPSLongitude")
        if got_lat is None and "QuickTime:GPSCoordinates" in actual:
            # video: "lat lon alt"
            try:
                parts = str(actual["QuickTime:GPSCoordinates"]).split()
                got_lat, got_lon = float(parts[0]), float(parts[1])
            except (ValueError, IndexError):
                got_lat = got_lon = None
        try:
            if got_lat is not None and got_lon is not None:
                if abs(float(got_lat) - exp_lat) <= 0.0001 and abs(float(got_lon) - exp_lon) <= 0.0001:
                    res.gps_status = "PASS"
                else:
                    res.gps_status = "FAIL"
                    res.notes.append(
                        f"GPS mismatch — expected ({exp_lat}, {exp_lon}), got ({got_lat}, {got_lon})"
                    )
            else:
                res.gps_status = "FAIL"
                res.notes.append(f"GPS missing — expected ({exp_lat}, {exp_lon})")
        except (ValueError, TypeError):
            res.gps_status = "FAIL"
            res.notes.append("GPS unparseable")

    # ------- Description check
    expected_desc = (rec.json_data.get("description") or "").strip()
    if expected_desc:
        got_desc = (actual.get("EXIF:ImageDescription")
                    or actual.get("XMP:Description") or "").strip()
        if got_desc == expected_desc:
            res.desc_status = "PASS"
        else:
            res.desc_status = "FAIL"
            res.notes.append(f"description mismatch — expected {expected_desc!r}, got {got_desc!r}")

    # ------- Favorited → Rating=5 check
    if rec.json_data.get("favorited"):
        rating = actual.get("XMP:Rating")
        try:
            if rating is not None and int(rating) == 5:
                res.fav_status = "PASS"
            else:
                res.fav_status = "FAIL"
                res.notes.append(f"favorited but Rating!=5 (got {rating})")
        except (ValueError, TypeError):
            res.fav_status = "FAIL"
            res.notes.append(f"favorited but Rating unparseable (got {rating})")

    return res


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------


def render_report(args, total: int, sampled: list[FileRecord],
                  results: list[CheckResult]) -> str:
    lines: list[str] = []
    lines.append(f"# galbum production verification — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append(f"- Root: `{args.root}`")
    lines.append(f"- Total media files walked: **{total}**")
    lines.append(f"- Sample size: **{len(sampled)}** ({len(sampled) / total * 100:.1f}% of total)" if total else "")
    lines.append(f"- RNG seed: `{args.seed}`")
    lines.append(f"- Sample target: {'limit ' + str(args.limit) if args.limit else f'{args.sample_pct * 100:.0f}%'}")
    lines.append("")

    # Per-check summary
    def tally(field):
        return Counter(getattr(r, field) for r in results)

    lines.append("## Summary")
    lines.append("")
    lines.append("| Check | PASS | FAIL | N/A |")
    lines.append("|---|---:|---:|---:|")
    for check in ("date_status", "gps_status", "desc_status", "fav_status"):
        t = tally(check)
        lines.append(f"| {check[:-7].upper()} | {t.get('PASS', 0)} | {t.get('FAIL', 0)} | {t.get('NA', 0)} |")
    lines.append("")

    # OTO consistency tally — informational, separate from PASS/FAIL.
    oto_t = tally("oto_status")
    lines.append("## OTO consistency (informational)")
    lines.append("")
    lines.append("EXIF:OffsetTimeOriginal vs DTO's embedded offset suffix. "
                 "STALE = the file has DTO with one offset but OTO with a different value "
                 "(timezone-shift risk for any reader that prioritises OTO over DTO's suffix). "
                 "MISSING = DTO embeds an offset but OTO tag is absent. "
                 "Both classes are galbum write-time gaps — date data is still correct, but "
                 "the metadata is internally inconsistent.")
    lines.append("")
    lines.append("| Status | Count |")
    lines.append("|---|---:|")
    for status in ("CONSISTENT", "STALE", "MISSING", "NAIVE", "NA"):
        lines.append(f"| {status} | {oto_t.get(status, 0)} |")
    lines.append("")

    # Per-bucket OTO breakdown for the STALE class — to know which file types matter.
    stale_results = [r for r in results if r.oto_status == "STALE"]
    if stale_results:
        lines.append(f"### STALE breakdown by sidecar tier evidence ({len(stale_results)} files)")
        lines.append("")
        stale_buckets = Counter()
        for r in stale_results:
            has_gps = bucket_key(r.rec)[2]
            stale_buckets[(r.rec.media.suffix.lower(), has_gps,
                           r.oto_dto_offset, r.oto_oto_value)] += 1
        lines.append("| ext | json_gps | DTO offset | OTO value | count |")
        lines.append("|---|---|---|---|---:|")
        for (ext, gps, dto_off, oto_off), count in sorted(stale_buckets.items(), key=lambda x: -x[1]):
            lines.append(f"| {ext} | {gps} | {dto_off} | {oto_off} | {count} |")
        lines.append("")

    # Bucket pass-rate
    by_bucket: dict[tuple, list[CheckResult]] = defaultdict(list)
    for r in results:
        by_bucket[bucket_key(r.rec)].append(r)
    lines.append("## Per-bucket coverage")
    lines.append("")
    lines.append("| match_type | sidecar_format | gps | type | failed | sampled | date PASS | gps PASS | total FAIL |")
    lines.append("|---|---|---|---|---|---:|---:|---:|---:|")
    for bucket in sorted(by_bucket.keys()):
        rs = by_bucket[bucket]
        date_pass = sum(1 for r in rs if r.date_status == "PASS")
        gps_pass = sum(1 for r in rs if r.gps_status == "PASS")
        any_fail = sum(1 for r in rs if "FAIL" in (r.date_status, r.gps_status, r.desc_status, r.fav_status))
        lines.append(f"| {bucket[0]} | {bucket[1]} | {bucket[2]} | {bucket[3]} | {bucket[4]} | "
                     f"{len(rs)} | {date_pass} | {gps_pass} | {any_fail} |")
    lines.append("")

    # Failure details
    failures = [r for r in results
                if any(s == "FAIL" for s in (r.date_status, r.gps_status, r.desc_status, r.fav_status))]
    lines.append(f"## Failures ({len(failures)})")
    lines.append("")
    if not failures:
        lines.append("_No failures._")
    else:
        for fr in failures[:200]:
            try:
                rel = fr.rec.media.relative_to(args.root)
            except ValueError:
                rel = fr.rec.media
            lines.append(f"### `{rel}`")
            lines.append(f"- match_type: `{fr.rec.match_type}`, sidecar_format: `{fr.rec.sidecar_format}`, video: `{fr.rec.is_video}`")
            lines.append(f"- date={fr.date_status}  gps={fr.gps_status}  desc={fr.desc_status}  fav={fr.fav_status}")
            for note in fr.notes:
                lines.append(f"  - {note}")
            lines.append("")
        if len(failures) > 200:
            lines.append(f"_… {len(failures) - 200} more failures truncated._")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                    help=f"Production extraction root (default: {DEFAULT_ROOT})")
    ap.add_argument("--sample-pct", type=float, default=DEFAULT_SAMPLE_PCT,
                    help=f"Fraction to sample (default: {DEFAULT_SAMPLE_PCT})")
    ap.add_argument("--limit", type=int, default=None,
                    help="Override sample-pct: cap total sample at this many files (smoke test)")
    ap.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility")
    ap.add_argument("--output", type=Path, default=None,
                    help="Output markdown path (default: verify-report-YYYYMMDD-HHMM.md at repo root)")
    ap.add_argument("--list-stale-paths", type=Path, default=None,
                    help="Also write the absolute path of every STALE file to this path "
                         "(one per line). Format matches galbum's failures.txt for use with "
                         "`galbum sync --retry-failures`. Forces --sample-pct 1.0.")
    ap.add_argument("--list-missing-paths", type=Path, default=None,
                    help="Also write the absolute path of every MISSING-OTO file to this "
                         "path (one per line). Same format/use as --list-stale-paths. "
                         "Forces --sample-pct 1.0.")
    ap.add_argument("--paths-from", type=Path, default=None,
                    help="Verify only files listed in this text file (one path per line). "
                         "Disables sampling; every listed path is checked.")
    args = ap.parse_args(argv)

    if not args.root.exists():
        print(f"Root does not exist: {args.root}", file=sys.stderr)
        return 2

    # --list-stale-paths or --list-missing-paths implies a full scan
    # (we need every affected file, no sampling).
    if args.list_stale_paths is not None or args.list_missing_paths is not None:
        args.sample_pct = 1.0
        args.limit = None

    print(f"[1/4] Walking {args.root} …", flush=True)
    records = walk_and_match(args.root)
    total = len(records)
    print(f"      {total} media files found.", flush=True)

    # If --paths-from is set, restrict to that explicit set; skip sampling.
    if args.paths_from is not None:
        wanted = {Path(line.strip()) for line in
                  args.paths_from.read_text(encoding="utf-8").splitlines()
                  if line.strip()}
        sampled = [r for r in records if r.media in wanted]
        missing = wanted - {r.media for r in sampled}
        print(f"[2/4] --paths-from restricted to {len(sampled)} of "
              f"{len(wanted)} requested paths "
              f"({len(missing)} not found in root).", flush=True)
        if missing and len(missing) <= 5:
            for m in missing:
                print(f"        not found: {m}", flush=True)
    else:
        print(f"[2/4] Stratified sampling …", flush=True)
        sampled = stratified_sample(records, args.sample_pct, args.seed, args.limit)
        print(f"      {len(sampled)} sampled.", flush=True)

    print(f"[3/4] Reading tags via exiftool (chunks of {EXIFTOOL_BATCH}) …", flush=True)
    with ExiftoolProcess() as et:
        actuals = batch_read_tags([r.media for r in sampled], et)
    print(f"      {len(actuals)} records read.", flush=True)

    print(f"[4/4] Comparing …", flush=True)
    results = [compare_one(r, actuals.get(r.media, {})) for r in sampled]

    out_path = args.output or Path.cwd() / f"verify-report-{datetime.now().strftime('%Y%m%d-%H%M')}.md"
    out_path.write_text(render_report(args, total, sampled, results), encoding="utf-8")
    print(f"Report written to {out_path}", flush=True)

    if args.list_stale_paths is not None:
        stale = [str(r.rec.media) for r in results if r.oto_status == "STALE"]
        args.list_stale_paths.write_text(
            "\n".join(stale) + ("\n" if stale else ""), encoding="utf-8"
        )
        print(f"STALE path list ({len(stale)} files) written to "
              f"{args.list_stale_paths}", flush=True)

    if args.list_missing_paths is not None:
        missing = [str(r.rec.media) for r in results if r.oto_status == "MISSING"]
        args.list_missing_paths.write_text(
            "\n".join(missing) + ("\n" if missing else ""), encoding="utf-8"
        )
        print(f"MISSING path list ({len(missing)} files) written to "
              f"{args.list_missing_paths}", flush=True)

    failures = sum(1 for r in results
                   if any(s == "FAIL" for s in (r.date_status, r.gps_status, r.desc_status, r.fav_status)))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
