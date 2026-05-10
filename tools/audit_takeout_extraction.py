"""
Audit Google Takeout extraction completeness.

For every zip we have:
  - List its claimed contents
  - Verify each entry exists on disk under <extract-root>/Takeout/...
  - Report any zip-claimed files that are missing on disk

For zip indices we DON'T have:
  - Cross-reference against any "loose" media files at the zip directory
    (Google extracts very large videos out of zips into the archive root,
     named like ``IMG_2063-031.MOV`` where ``031`` is the zip index it
     would have lived in had it fit). A loose media file accounts for an
     otherwise-missing zip index.
  - Report any genuinely missing indices (no zip, no loose media)

Usage:
  python audit_takeout_extraction.py                 # uses defaults
  python audit_takeout_extraction.py --zip-dir <dir> --extract-root <dir> \\
                                     --zip-pattern <glob>

Defaults match the May 2026 Takeout export at
``D:\\Dropbox\\應用程式\\Google Download Your Data`` extracted to
``D:\\Takeout-0508``.
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

# Pattern: ``<basename>-<zipidx>.<ext>`` — Google's naming for split-out large media
LOOSE_MEDIA_RE = re.compile(r"^(?P<base>.+?)-(?P<idx>\d{3})\.(?P<ext>MOV|MP4|mov|mp4)$")


def _on_disk_path(extract_root: Path, zip_relpath: str) -> Path:
    """Resolve a zip-internal path to an on-disk path, applying Windows
    naming-rule normalisation: NTFS quietly strips trailing periods and
    spaces from path components when accessed via the Win32 API. The file
    can still exist (POSIX tools see it) but Python's pathlib cannot. Strip
    those characters from each path component to match what Python will
    actually find on disk.
    """
    parts = []
    for part in zip_relpath.replace("\\", "/").split("/"):
        cleaned = part.rstrip(". ")
        parts.append(cleaned if cleaned else part)
    return extract_root.joinpath(*parts)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--zip-dir", type=Path,
                   default=Path("D:/Dropbox/應用程式/Google Download Your Data"),
                   help="directory containing the *.zip files (also where "
                        "Google places loose large videos)")
    p.add_argument("--extract-root", type=Path,
                   default=Path("D:/Takeout-0508"),
                   help="directory the zips were extracted to (parent of "
                        "the ``Takeout/`` folder)")
    p.add_argument("--zip-pattern", default="takeout-20260508T042450Z-3-*.zip",
                   help="glob pattern matching the data zips (NOT the manifest)")
    p.add_argument("--show-missing", type=int, default=10,
                   help="how many missing-file paths to list per zip")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    zips = sorted(args.zip_dir.glob(args.zip_pattern))
    if not zips:
        print(f"No zips found matching {args.zip_dir / args.zip_pattern}")
        return 1

    # Loose media files at the zip directory (Google extracts these out of zips
    # when they're too large to fit). Indexed by the zip index they would have
    # lived in.
    loose_by_idx: dict[int, list[Path]] = {}
    for f in sorted(args.zip_dir.iterdir()):
        if not f.is_file():
            continue
        m = LOOSE_MEDIA_RE.match(f.name)
        if m:
            loose_by_idx.setdefault(int(m.group("idx")), []).append(f)

    indices_present = sorted(int(z.stem.rsplit("-", 1)[1]) for z in zips)
    expected_range = list(range(indices_present[0], indices_present[-1] + 1))
    indices_missing_zip = sorted(set(expected_range) - set(indices_present))
    indices_explained_by_loose = [i for i in indices_missing_zip if i in loose_by_idx]
    indices_genuinely_missing = [i for i in indices_missing_zip if i not in loose_by_idx]

    print(f"Zip directory:      {args.zip_dir}")
    print(f"Extract root:       {args.extract_root}")
    print(f"Pattern:            {args.zip_pattern}")
    print()
    print(f"Zips present:                       {len(zips):>4}  "
          f"(indices {indices_present[0]:03d}..{indices_present[-1]:03d})")
    print(f"Zip indices absent:                 {len(indices_missing_zip):>4}  "
          f"→ {indices_missing_zip}")
    if loose_by_idx:
        loose_count = sum(len(v) for v in loose_by_idx.values())
        print(f"Loose split-out media files:        {loose_count:>4}  "
              f"(account for {len(indices_explained_by_loose)} of the absent indices)")
        if indices_genuinely_missing:
            print(f"Indices with NEITHER zip nor loose: {len(indices_genuinely_missing):>4}  "
                  f"→ {indices_genuinely_missing}")
    print()

    total_zip_entries = 0
    total_zip_bytes = 0
    total_present_on_disk = 0
    total_missing_on_disk = 0
    per_zip_missing: dict[str, list[str]] = {}

    print(f"{'zip':>4}  {'entries':>7}  {'on-disk':>7}  {'MISSING':>7}  {'GB':>6}")
    print("-" * 50)

    for z in zips:
        idx = int(z.stem.rsplit("-", 1)[1])
        try:
            with zipfile.ZipFile(z) as zf:
                entries = zf.infolist()
        except (zipfile.BadZipFile, OSError) as exc:
            print(f"{idx:4d}  ZIP UNREADABLE: {exc}")
            continue

        files = [e for e in entries if not e.is_dir()]
        zip_bytes = sum(e.file_size for e in files)

        present = 0
        missing_paths: list[str] = []
        for e in files:
            on_disk = _on_disk_path(args.extract_root, e.filename)
            if on_disk.exists():
                present += 1
            else:
                missing_paths.append(e.filename)

        total_zip_entries += len(files)
        total_zip_bytes += zip_bytes
        total_present_on_disk += present
        total_missing_on_disk += len(missing_paths)
        if missing_paths:
            per_zip_missing[z.name] = missing_paths

        gb = zip_bytes / (1024 ** 3)
        flag = "" if not missing_paths else "  ←!"
        print(f"{idx:4d}  {len(files):7d}  {present:7d}  {len(missing_paths):7d}  {gb:6.2f}{flag}")

    print("-" * 50)
    print(f" tot  {total_zip_entries:7d}  {total_present_on_disk:7d}  "
          f"{total_missing_on_disk:7d}  {total_zip_bytes/(1024**3):6.2f}")
    print()
    print(f"Files claimed by present zips:        {total_zip_entries:>10}")
    print(f"  of which present on disk:           {total_present_on_disk:>10}")
    print(f"  of which MISSING on disk:           {total_missing_on_disk:>10}")
    print()

    if per_zip_missing:
        print("=" * 70)
        print(f"ZIPS WITH FILES MISSING FROM DISK ({len(per_zip_missing)} zips affected)")
        print("=" * 70)
        for zname, paths in sorted(per_zip_missing.items()):
            print(f"\n{zname}  →  {len(paths)} missing:")
            for p in paths[:args.show_missing]:
                print(f"    {p}")
            if len(paths) > args.show_missing:
                print(f"    ... and {len(paths) - args.show_missing} more")
        print()

    if loose_by_idx:
        print("=" * 70)
        print(f"LOOSE SPLIT-OUT MEDIA FILES (need placement in album folders)")
        print("=" * 70)
        for idx in sorted(loose_by_idx):
            for f in loose_by_idx[idx]:
                size_gb = f.stat().st_size / (1024 ** 3)
                print(f"  zip-{idx:03d}  {f.name}  ({size_gb:.2f} GB)")
        print()

    print("=" * 70)
    if not per_zip_missing and not indices_genuinely_missing:
        print("VERDICT: ✓ All present zips fully extracted; absent zip indices are "
              "all accounted for by loose split-out media files.")
        return 0
    if indices_genuinely_missing and not per_zip_missing:
        print(f"VERDICT: Present zips OK, but {len(indices_genuinely_missing)} zip "
              f"indices have NO source (no zip, no loose file). Content from those "
              f"is missing — re-download from Takeout if needed.")
        return 1
    print("VERDICT: Extraction incomplete — see per-zip missing-file lists above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
