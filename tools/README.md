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
