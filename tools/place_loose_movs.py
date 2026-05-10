"""
Place Google-Takeout's split-out large videos into their album folders.

Google extracts videos that don't fit in a zip (>~10 GB compressed segment) as
loose files at the archive root, named ``<basename>-<zipidx>.MOV``. Each one's
JSON sidecar (``<basename>.MOV.supplemental-metadata.json``) is in some other
zip, and after extraction lives somewhere under ``Takeout/Google 相簿/<album>/``.

This script:
  1. Lists every loose ``-NNN.MOV`` file at --zip-dir
  2. For each, finds matching JSON sidecars in the extracted tree
  3. Copies (or symlinks, with --link) the MOV next to each matching JSON

When the same basename has multiple loose copies (e.g. three IMG_2063 files
with different zip indices), we treat them as DISTINCT videos that happen to
share an iPhone counter — each gets placed independently. If the count of
loose files exceeds the count of JSON sidecars for that basename, the extras
are reported and left at the zip-dir root for manual triage.

Usage:
  python place_loose_movs.py [--dry-run] [--link]

Defaults match the May 2026 Takeout layout.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from collections import defaultdict

# Loose split-out media: ``<base>-<NNN>.<ext>`` at the archive root.
# ``<base>`` may itself carry a ``(N)`` disambiguator when the same media
# appears in multiple albums (e.g. ``IMG_2063(1)-058.MOV``).
LOOSE_RE = re.compile(r"^(?P<base>.+?)-(?P<idx>\d{3})\.(?P<ext>MOV|MP4|mov|mp4)$")
DUPE_RE = re.compile(r"^(?P<stem>.+?)\((?P<n>\d+)\)$")


def canonical_media_name(loose_name: str) -> str:
    """Derive the original media filename from a loose split-out filename.

    ``IMG_2063-031.MOV`` → ``IMG_2063.MOV``
    ``IMG_2063(1)-058.MOV`` → ``IMG_2063.MOV`` (the ``(1)`` disambiguator
    means "this is the second copy of the same media", not a different file)
    """
    m = LOOSE_RE.match(loose_name)
    if not m:
        return loose_name
    base, ext = m.group("base"), m.group("ext").upper()
    # Strip any (N) disambiguator from the base
    dupe = DUPE_RE.match(base)
    if dupe:
        base = dupe.group("stem")
    return f"{base}.{ext}"


def find_jsons_for_media(media_filename: str, extract_root: Path) -> list[Path]:
    """All sidecar JSONs in the extracted tree whose `title` field matches
    `media_filename`. Title-based matching is robust to:

    - The 5+ supplemental-metadata suffix truncation variants
    - ``(N)`` disambiguators appearing anywhere in the JSON filename
    - Heavily-truncated basenames (where the JSON's filename is too short
      to recover the full media name from)

    Searches all JSON sidecars under `extract_root`. Caches title reads
    across calls would be a useful optimisation if invoked many times;
    for the ~10-MOV use case we just rglob each call.
    """
    matches: list[Path] = []
    # rglob over every plausible JSON pattern in the extracted tree.
    for json_path in extract_root.rglob("*.json"):
        # Skip top-level album-meta files (no title field)
        if json_path.name in ("中繼資料.json", "metadata.json"):
            continue
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        if data.get("title") == media_filename:
            matches.append(json_path)
    # Sort for deterministic output
    return sorted(matches)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--zip-dir", type=Path,
                   default=Path("D:/Dropbox/應用程式/Google Download Your Data"))
    p.add_argument("--extract-root", type=Path,
                   default=Path("D:/Takeout-0508"))
    p.add_argument("--dry-run", action="store_true",
                   help="report planned actions without copying")
    p.add_argument("--link", action="store_true",
                   help="hardlink instead of copy (saves disk; same volume only)")
    args = p.parse_args()

    if not args.zip_dir.is_dir():
        print(f"--zip-dir not a directory: {args.zip_dir}")
        return 1
    if not args.extract_root.is_dir():
        print(f"--extract-root not a directory: {args.extract_root}")
        return 1

    # Group loose MOVs by *canonical* media name (strips ``-NNN`` and any
    # ``(N)`` from the basename). Multiple loose copies with the same canonical
    # name are siblings — same underlying video stored in multiple albums.
    loose_by_canonical: dict[str, list[Path]] = defaultdict(list)
    for f in sorted(args.zip_dir.iterdir()):
        if f.is_file() and LOOSE_RE.match(f.name):
            canonical = canonical_media_name(f.name)
            loose_by_canonical[canonical].append(f)

    if not loose_by_canonical:
        print(f"No loose -NNN.MOV files at {args.zip_dir}")
        return 0

    total_loose = sum(len(v) for v in loose_by_canonical.values())
    print(f"Found {total_loose} loose video files "
          f"across {len(loose_by_canonical)} canonical names\n")

    placed = 0
    failed = 0

    for media_filename, loose_files in sorted(loose_by_canonical.items()):
        sidecars = find_jsons_for_media(media_filename, args.extract_root)
        loose_count = len(loose_files)
        sidecar_count = len(sidecars)

        if not sidecars:
            print(f"  ⚠  {media_filename}: NO sidecar found in extracted tree "
                  f"({loose_count} loose copy/copies)")
            for lf in loose_files:
                print(f"     orphan: {lf.name}")
            failed += loose_count
            continue

        if loose_count != sidecar_count:
            print(f"  ⚠  {media_filename}: {loose_count} loose vs {sidecar_count} "
                  f"sidecars (mismatch)")

        # Pair them up. For now, use a simple zip — index N → sidecar N.
        # This isn't perfect when counts differ, but it's a starting point.
        pairs = list(zip(loose_files, sidecars))
        for loose, sidecar in pairs:
            target = sidecar.parent / media_filename
            if target.exists() and target.stat().st_size == loose.stat().st_size:
                print(f"  ✓ already placed: {target.relative_to(args.extract_root)}")
                placed += 1
                continue

            print(f"  → {loose.name}  →  {target.relative_to(args.extract_root)}")
            if not args.dry_run:
                try:
                    if args.link:
                        target.hardlink_to(loose)
                    else:
                        shutil.copy2(loose, target)
                    placed += 1
                except (OSError, shutil.Error) as exc:
                    print(f"     !! failed: {exc}")
                    failed += 1

        if loose_count > sidecar_count:
            extras = loose_files[sidecar_count:]
            print(f"     extras (no sidecar to pair with):")
            for extra in extras:
                print(f"       {extra.name}")
                failed += 1

    print()
    print(f"Placed: {placed}    Failed/orphaned: {failed}")
    if args.dry_run:
        print("(dry-run — nothing actually copied)")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
