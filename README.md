# Google Album Metadata Tools

Utilities for writing Google Photos Takeout JSON metadata back into your media files using [ExifTool](https://exiftool.org/).

When you export your library via Google Takeout, every photo and video comes with a `.json` sidecar containing the original timestamp, GPS coordinates, description, and favourite flag — but that data is **not** embedded in the file itself. These tools fix that.

---

## sync_takeout.py (Python — recommended)

A single-file Python script that processes an entire Takeout export in one pass. It uses a persistent `exiftool -stay_open` process for speed and handles the many filename edge-cases that appear in real Takeout exports.

### Prerequisites

- **Python 3.9+** (uses `zoneinfo`, available from 3.9)
- **ExifTool** — install from <https://exiftool.org/> and ensure it is on your `PATH`
- **timezonefinder** *(optional)* — if installed, timestamps are written in the photo's local timezone (derived from GPS coordinates); otherwise UTC is used

```bash
pip install timezonefinder   # optional but recommended
```

### Quick start

```bash
# 1. Clone the repo
git clone https://github.com/jackal998/google-album-metadata.git
cd google-album-metadata

# 2. (Optional) install the timezone dependency
pip install -r requirements.txt

# 3. Point the script at your Takeout album root and do a dry run first
python sync_takeout.py --root "/path/to/Takeout/Google Photos" --dry-run

# 4. Run for real
python sync_takeout.py --root "/path/to/Takeout/Google Photos"
```

The `--root` flag is required unless you edit the `DEFAULT_ROOT` constant near the top of the script to match your local path.

### All options

| Flag | Description |
|---|---|
| `--root PATH` | Root album folder containing per-album subdirectories |
| `--folder NAME` | Process only this subfolder (repeatable) |
| `--test-only` | Process only the `測試` test folder |
| `--dry-run` | Preview what would be written without touching any files |
| `--force` | Re-process files that already have `DateTimeOriginal` |
| `--backup` | Keep exiftool `_original` backups (omits `-overwrite_original`) |
| `--no-file-dates` | Do not update OS-level file creation/modification timestamps |
| `--exclude NAME` | Skip this subfolder name (repeatable) |
| `--retry-failures` | Re-process only the files listed in `failures.txt` |
| `--log PATH` | Log file path (default: `sync_takeout.log`) |

### JSON matching

The script uses a five-step algorithm to pair each media file with its sidecar JSON:

1. **Exact** — `IMG_9556.HEIC` → `IMG_9556.HEIC.json`
2. **Duplicate reorder** — `IMG_9556(1).HEIC` → `IMG_9556.HEIC(1).json`
3. **Live-photo video orphan** — `IMG_9556.MP4` → `IMG_9556.HEIC.json`
4. **Edited-photo fallback** — `IMG_3818-已編輯.HEIC` → `IMG_3818.HEIC.json`
5. **Title-field prefix match** — handles UUID truncation in both directions

### Output files

After a run, the script writes two optional summary files next to itself:

- **`orphans.txt`** — media files for which no JSON could be matched
- **`failures.txt`** — files where JSON was found but processing failed; pass `--retry-failures` on the next run to attempt them again

Both files are gitignored.

---

## galbumtool (Ruby — legacy)

An earlier Ruby-based CLI with a more elaborate error-handling pipeline. It copies files to a destination directory while applying metadata, and produces a CSV output file.

### Prerequisites

- Ruby 3.x
- Bundler
- ExifTool on `PATH`

### Setup

```bash
bundle install
```

### Usage

```bash
# Normal processing
bin/galbumtool -s <source_directory> -d <destination_directory>

# Process error files from a previous run
bin/galbumtool --process-errors -d <destination_directory>

# Show version
bin/galbumtool --version
```

---

## License

MIT — see [LICENSE](LICENSE).
