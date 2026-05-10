# tools/

Operational helpers used around Google Takeout extractions. Not part of the
`galbum` package — these are standalone scripts you run before or after the
main `galbum sync` flow when working with a fresh Takeout dump.

Defaults in both scripts target the May-2026 Takeout layout (`takeout-2026...`
zips extracted to `D:\Takeout-...`); both accept `--zip-dir` and
`--extract-root` overrides for other layouts.

## `audit_takeout_extraction.py`

Run after extracting a fresh Takeout to confirm completeness, before
`galbum sync`. For each zip we still have, it lists the zip's claimed contents
and verifies every entry exists on disk. For zip indices we no longer have
(deleted to save space), it cross-references against "loose" media files at
the archive root — Google extracts very large videos out of zips into the
archive root with names like `IMG_2063-031.MOV`, where `031` is the zip index
the file would have lived in.

```
python tools/audit_takeout_extraction.py
python tools/audit_takeout_extraction.py --zip-dir <dir> --extract-root <dir>
```

## `place_loose_movs.py`

Run after extraction when Google has split out large videos as
`<base>-NNN.MOV` at the archive root. The matching JSON sidecar lives in some
other zip and after extraction ends up under
`Takeout/Google 相簿/<album>/`. This script walks the loose files, finds
matching sidecars in the extracted tree, and copies (or symlinks, with
`--link`) each MOV next to each matching JSON so `galbum sync` picks them up.

When the same basename has multiple loose copies (e.g. three `IMG_2063` files
with different zip indices), they're treated as DISTINCT videos that happen
to share an iPhone counter; each gets placed independently. Extras beyond the
sidecar count are reported and left at the archive root for manual triage.

```
python tools/place_loose_movs.py --dry-run
python tools/place_loose_movs.py --link
```

## `verify_production_tags.py`

Run after `galbum sync` to verify the metadata that was actually written
matches the JSON sidecar source-of-truth. Walks the extracted Takeout tree,
classifies each media file by edge-case bucket (match-type / sidecar format /
tier evidence), draws a stratified sample, batch-reads tags via persistent
exiftool, compares against the JSON, and emits a markdown report covering
DATE / GPS / DESC / FAV correctness plus an OTO consistency section.

```
python tools/verify_production_tags.py                               # 15% sample
python tools/verify_production_tags.py --sample-pct 1.0              # full scan
python tools/verify_production_tags.py --limit 30                    # smoke test
```

The script is read-only — it never writes EXIF, never moves files. Safe to
run repeatedly. Defaults match the May-2026 Takeout layout; override
with `--root <path>`.

### Targeted backfill workflow

When verification surfaces a class of inconsistency (e.g. STALE OTO from
a pre-PR-#12 write), pair this script with `galbum sync --retry-failures`
for surgical cleanup:

```bash
# 1. Identify impacted files (full scan, paths-only output)
python tools/verify_production_tags.py \
  --list-stale-paths /tmp/stale-paths.txt \
  --list-missing-paths /tmp/missing-paths.txt \
  --output /tmp/full-scan-report.md

# 2. Targeted re-write via galbum's existing retry plumbing
mkdir backfill && cd backfill
cp /tmp/stale-paths.txt failures.txt
python -m galbum sync --retry-failures --force "<root>"

# 3. Re-verify only the impacted files
python tools/verify_production_tags.py \
  --paths-from /tmp/stale-paths.txt \
  --output /tmp/post-fix-report.md
```

`--list-stale-paths` and `--list-missing-paths` force a 100% scan and emit
absolute paths in the format `galbum sync --retry-failures` consumes
(`failures.txt` lines). `--paths-from FILE` restricts verification to a
specific path list; useful for confirming a targeted fix landed without
re-walking the whole library.
