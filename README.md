# Google Album Metadata Tools (`galbum`)

Write Google Photos Takeout JSON metadata back into your media files using [ExifTool](https://exiftool.org/).

When you export your library via Google Takeout, every photo and video comes with a JSON sidecar containing the original timestamp, GPS coordinates, description, and favourite flag — but that data is **not** embedded in the file itself. `galbum` reverses that loss in place: walk the extracted Takeout, match each media file to its sidecar, write the metadata back via ExifTool.

---

## Compatibility

- **Operating systems:** Windows 10 / 11, macOS, Linux. Most heavily exercised on Windows 10/11 against Takeouts of 13,000+ files.
- **Python:** 3.10+
- **ExifTool:** required, must be on `PATH`
- **Takeout formats supported:**
  - Legacy plain `.json` sidecars (pre-2026 exports)
  - May-2026+ `.supplemental-metadata.json` family — full suffix and all five MAX-PATH-driven truncation variants (`.supplemental-metadat.json` … `.supplemental-meta.json`), with the `(N)` duplicate disambiguator placed inside the suffix as Google actually emits it
  - Mixed-format folders (some legacy, some new) Just Work — both forms collapse to the same lookup key

---

## Prerequisites

- **Python 3.10+**
- **ExifTool** — install from <https://exiftool.org/> and ensure `exiftool --version` works from any shell.
- **timezonefinder** *(optional but recommended)* — when installed, timestamps are written in the photo's local timezone (derived from JSON GPS); otherwise UTC fallback.

```bash
pip install -r requirements.txt   # installs timezonefinder + tzdata (the latter is required on Windows)
```

### Windows-specific notes

- Install ExifTool by downloading the Windows zip from <https://exiftool.org/>, renaming `exiftool(-k).exe` → `exiftool.exe`, and adding the folder to your `PATH`.
- **`tzdata` is required on Windows.** It ships with Linux/macOS but not Windows; without it, `ZoneInfo` GPS-based timezone resolution fails. `requirements.txt` already includes it.
- Paths with spaces or non-ASCII characters (`Google 相簿`, `2024 年的相片`) work fine — quote them in PowerShell / cmd.
- Some Takeout-extraction edge cases on Windows surface as known limitations — see [Known limitations on Windows](#known-limitations-on-windows) below.

---

## Quick start

```bash
# 1. Clone the repo
git clone https://github.com/jackal998/google-album-metadata.git
cd google-album-metadata

# 2. Install timezone deps (optional — without this, dates fall back to UTC)
pip install -r requirements.txt

# 3. Dry run first — preview what would be written without touching any files
galbum sync "/path/to/Takeout/Google Photos" --dry-run

# 4. Run for real
galbum sync "/path/to/Takeout/Google Photos"

# 5. Or run from inside the album folder (path defaults to current directory)
cd "/path/to/Takeout/Google Photos"
galbum sync
```

The folder name varies by your Google account language. English: `Google Photos`. Traditional Chinese: `Google 相簿`. Pass whichever your Takeout produced.

You can also invoke without installing the entry point:

```bash
python -m galbum sync "/path/to/Takeout/Google Photos" --dry-run
```

---

## All options

```
galbum sync [path] [options]
```

| Argument / Flag | Description |
|---|---|
| `path` | Root album folder containing per-album subdirectories (default: current directory) |
| `--folder NAME` | Process only this subfolder (repeatable) |
| `--test-only` | Process only the `測試` test folder |
| `--dry-run` | Preview what would be written without touching any files |
| `--force` | Re-process files that already have `DateTimeOriginal` |
| `--backup` | Keep ExifTool `_original` backups (omits `-overwrite_original`) |
| `--no-file-dates` | Do not update OS-level file creation/modification timestamps |
| `--exclude NAME` | Skip this subfolder name (repeatable) |
| `--retry-failures` | Re-process only files listed in `failures.txt` (targeted retry, no full scan) |
| `--log PATH` | Log file path (default: `galbum.log`) |

---

## How matching works

For each media file, `galbum` runs a 5-step algorithm to find its JSON sidecar:

1. **Exact match** — `IMG_9556.HEIC` → `IMG_9556.HEIC.json` (legacy) or `IMG_9556.HEIC.supplemental-metadata.json` (new format, including all 5 truncation variants)
2. **Duplicate reorder** — `IMG_9556(1).HEIC` → `IMG_9556.HEIC(1).json` / `IMG_9556.HEIC.supplemental-metadata(1).json`
3. **Live-photo video orphan** — `IMG_9556.MP4` borrows the same-stem photo's sidecar
4. **Edited-photo fallback** — `IMG_3818-已編輯.HEIC` → strip the localised "edited" suffix, retry exact match
5. **Title-field prefix match** — fallback to the JSON's own `"title"` field when the sidecar filename was heavily truncated by Google

A single regex covers every new-format suffix variant + inside-suffix `(N)`:

```
\.supplemental-meta(?:data|dat|da|d)?(\(\d+\))?\.json$
```

## How timezone is recovered

When the JSON's GPS is missing (Google often strips coordinates during export), `galbum` falls back through four tiers in order:

1. **JSON GPS** → `TimezoneFinder` lookup → IANA zone → offset
2. **EXIF `OffsetTimeOriginal`** in the file (recovers iPhone's recorded offset)
3. **IPTC `DigitalCreationDateTime`** (naive local) diffed against JSON UTC, accepted only when the implied offset is real-world plausible (within ±14h, aligned to 15 min — supports Nepal +05:45, Newfoundland −03:30, etc.)
4. **UTC fallback** when no offset evidence exists

Whichever tier wins, the resulting `DateTimeOriginal` and `OffsetTimeOriginal` are written together so the two tags can never drift out of sync.

---

## Output files

After a run, two optional summary files are written to the current working directory:

- **`orphans.txt`** — media files for which no JSON could be matched
- **`failures.txt`** — files where JSON was found but processing failed; pass `--retry-failures` on the next run to retry them

Both are gitignored.

---

## Verification workflow

After running `galbum sync`, you can confirm the metadata that was actually written matches the JSON sidecar source-of-truth by running:

```bash
python tools/verify_production_tags.py "/path/to/Takeout/Google Photos"
```

The script samples the library (default 15%, ensuring at least one file from every match-type / sidecar-format / GPS-state bucket), batch-reads tags via persistent ExifTool, compares against the JSONs, and writes a markdown report covering:

- DATE — file's UTC instant matches JSON `photoTakenTime`
- GPS — file's lat/lon match JSON within 0.0001°
- DESCRIPTION — file's description matches JSON
- FAVORITED — `XMP:Rating=5` set when JSON `favorited: true`
- OTO consistency — `OffsetTimeOriginal` matches `DateTimeOriginal`'s embedded offset (no internal drift)

The script is read-only — it never writes EXIF, never moves files. See [`tools/README.md`](tools/README.md) for the full surgical-backfill workflow (verify → targeted retry → re-verify) when a class of inconsistency surfaces.

---

## Tools

The `tools/` directory holds operational helpers used around Takeout extraction. All are standalone scripts; defaults target the May-2026+ layout, all accept overrides.

| Script | Purpose |
|---|---|
| [`audit_takeout_extraction.py`](tools/audit_takeout_extraction.py) | Verify every zip-claimed file extracted; cross-reference loose `-NNN.MOV` split-outs against missing zip indices. Run before `galbum sync`. |
| [`place_loose_movs.py`](tools/place_loose_movs.py) | Copy / symlink Google's split-out large videos (`<base>-NNN.MOV` at archive root) next to their album-folder sidecars so `galbum sync` can match them. |
| [`verify_production_tags.py`](tools/verify_production_tags.py) | Verify `galbum`'s output against JSON sidecar source-of-truth. See [Verification workflow](#verification-workflow). |

See [`tools/README.md`](tools/README.md) for full usage.

---

## Known limitations on Windows

- **Trailing-period folder names** — NTFS preserves names ending in `.` or whitespace (e.g. `E.J.`), but the Win32 GUI silently strips them. Such folders appear empty to most tools. `galbum` will skip / mis-route these. Fix: rename the album folder to drop the trailing character (`E.J.` → `E.J`).
- **Case-insensitive NTFS collisions** — `IMG_X.MOV` and `IMG_X.mov` cannot coexist in the same directory on case-insensitive NTFS (the default). Google Takeout occasionally produces both; one will silently overwrite the other on extraction. Fix: either enable case sensitivity per-directory (`fsutil file setCaseSensitiveInfo enable`, requires admin) or quarantine collisions to a sibling folder for manual triage.
- **Corrupt videos pre-flagged by Google** — files Google itself moved to `失敗的影片/` ("failed videos") tend to be malformed MP4 containers. ExifTool can't write to a broken atom tree, so `galbum` will log them in `failures.txt`. Not a `galbum` bug.

These are properties of the Takeout extraction / Windows filesystem, not `galbum`. The first two are documented further in [`docs/new-takeout-format-plan.md`](docs/new-takeout-format-plan.md).

---

## Development & testing

```bash
pip install -r requirements-dev.txt
# Linux / WSL: sudo apt-get install libimage-exiftool-perl
# macOS:       brew install exiftool
# Windows:     download from https://exiftool.org/
```

```bash
pytest tests/unit/ -q          # 247 unit tests; no exiftool needed
pytest -q                      # unit + e2e (exiftool must be on PATH)
pytest tests/e2e/ -v -m e2e    # e2e only
pytest -m local_fixtures -v    # opt-in real-data parity tests (requires a personal .local-fixtures/ — auto-skips otherwise)
```

### Test layout

```
tests/
  unit/
    test_filename_parsing.py   # parse_media_filename()
    test_json_matching.py      # find_json() — all 5 matching steps + new-format suffix family
    test_metadata_parsing.py   # parse_metadata(), is_valid_gps(), 4-tier _local_datetime()
    test_exiftool_args.py      # build_exiftool_args() per file type, including OTO consistency
    test_batch_read.py         # exiftool JSON parser + bind-by-SourceFile
    test_file_type.py          # get_file_type(), _magic_type(), mismatch detection
  e2e/
    test_e2e.py                # legacy-format pipeline against real fixture files
    test_e2e_new_format.py     # May-2026+ format pipeline (suffix variants, inside-suffix (N), title-match)
  fixtures/
    e2e_album/                 # legacy .json sidecars
    e2e_album_new_format/      # .supplemental-metadata.json family fixtures
  local/
    test_local_fixtures_format_parity.py   # opt-in: same source photo across both formats produces same parsed metadata
```

### CI

GitHub Actions runs the full unit + e2e matrix (Python 3.10 / 3.11 / 3.12) on every push and pull request, installing exiftool via `apt-get`.

---

## License

MIT — see [LICENSE](LICENSE).
