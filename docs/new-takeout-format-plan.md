# Support plan — Google Takeout May 2026 format

Plan for adapting `galbum` to handle Google Takeout exports created on/after
May 2026 (`takeout-20260508T...`). The format diverges from the previous one
in non-trivial ways, including a JSON sidecar suffix change that breaks the
current matcher silently.

This plan precedes implementation — it scopes the work, identifies risks,
and orders the changes so each one is independently shippable.

## Change inventory

Established by surveying ~1,000 JSONs and full extracted-tree exploration
of `D:\Takeout-0508\Takeout\Google 相簿\`.

### 1. JSON sidecar filename — new full form + truncation variants

| Old format | New format |
|---|---|
| `IMG_0022.HEIC.json` | `IMG_0022.HEIC.supplemental-metadata.json` |

When the full path would exceed Windows MAX_PATH (260 chars), Google
truncates **the suffix itself** (and then the basename if needed):

| Suffix variant | Frequency in sample |
|---|---|
| `.supplemental-metadata.json` | 836 (94%) |
| `.supplemental-metada.json` | 26 (3%) |
| `.supplemental-metadat.json` | 19 (2%) |
| `.supplemental-metad.json` | 1 |
| `.supplemental-meta.json` | 1 |
| heavily-truncated `.json` (basename also trimmed) | ~50 |

**Implication for `json_matching.py`:** every step that constructs a
candidate by appending `.json` is wrong. Need to handle 5–6 suffix
variants AND the case where the JSON's filename is truncated to less
than `<media>.<suppl-suffix>`.

The JSON's own `"title"` field always carries the original media filename,
even when the surrounding filename is heavily truncated. **The most robust
matcher uses `title` as primary key, filename pattern as fallback.**

### 2. JSON schema changes

| Field | Old | New | Notes |
|---|---|---|---|
| `geoData` | present | present | now the primary GPS source |
| `geoDataExif` | usually present | rare (~3.5%) | only when EXIF GPS differs from inferred |
| `favorited` | present (when starred) | present but rare (~2.5%) | user behaviour shift toward archive |
| `archived` | (not seen) | present (~52%) | NEW — user hid photo from main view |
| `imageViews`, `description`, `url`, `googlePhotosOrigin`, `creationTime`, `photoTakenTime`, `title` | present | present | unchanged |

### 3. Album folder names — localised, possibly with trailing-period landmines

| Old | New |
|---|---|
| `Photos from 2024` | `2024 年的相片` |
| (other album names) | (often Chinese, depending on user account language) |

Top-level non-album JSON files are also localised:

| Old | New |
|---|---|
| `user_generated_memory_titles.json` | `使用者-產生的-回憶集錦-名稱.json` |
| `shared_album_comments.json` | `共享_相簿_留言.json` |
| `print-subscriptions.json` | (not seen — may still exist in older exports) |

#### Trailing-period folder names — a Windows landmine

User-named albums whose name ends with `.` (e.g. `E.J.`) cause
trouble on Windows: NTFS lets `unzip` create the folder with the
literal trailing period preserved, but **the Win32 API silently strips
trailing periods**. The folder *appears* in directory listings, but
attempting to enumerate or open files inside it via Win32 (Python
pathlib, PowerShell, Explorer) returns empty — only POSIX-aware tools
(Git Bash `ls`, Cygwin) can see the contents.

Concrete example from the 0508 export: the `E.J.` album held 23 files
that the audit initially reported as missing on disk. Renaming the
folder to drop the trailing period (`E.J`) fixed accessibility.

**Galbum implications**:

1. The scanner should detect album-folder names ending in `.` or ` `
   (also stripped) and either:
   - Auto-rename to remove the trailing characters, OR
   - Warn the user with a clear "this folder is inaccessible to Windows
     tools — rename via `mv` to fix" message
2. The audit script should normalise zip-internal paths the same way
   when checking on-disk presence (already implemented in
   `tools/audit_takeout_extraction.py`).

### 4. Large-video split-out at archive root — same as before, with a Windows landmine

Google still extracts videos that won't fit in a ~10 GB compressed zip
segment as standalone files at the archive root, named
`<basename>-<zipidx>.MOV`. The pattern is unchanged from the previous
export. galbum doesn't currently handle these — they need manual
placement (or a galbum-side step) to land them next to their JSON
sidecars.

#### Windows case-collision pitfall

The same iPhone counter can host two genuinely-distinct videos that
differ only by filename CASE. Concrete example from the 0508 export:

```
Takeout/Google 相簿/2024 年的相片/IMG_2063.mov              ← 281 MB, in zip-057
Takeout/Google 相簿/2024 年的相片/IMG_2063.MOV.supplemental-metadata.json     ← sidecar for the .mov
Takeout/Google 相簿/2024 年的相片/IMG_2063.MOV.supplemental-metadata(1).json  ← sidecar for the loose 4.19 GB .MOV
```

The 4.19 GB MOV is split out as `IMG_2063-031.MOV` at the archive root.
**On Windows-default case-insensitive NTFS, `IMG_2063.mov` and
`IMG_2063.MOV` cannot coexist in the same directory** — a `cp` of one
silently overwrites the other.

This is a genuine data-integrity hazard. Mitigations:

1. **Detect-and-skip** — placement script must check whether a target
   filename collides case-insensitively with an existing entry, and if so
   either:
   - Skip placement and log the collision for user review, OR
   - Place the colliding file in a sibling `_collision/` subfolder
2. **Per-directory case-sensitivity** — Windows 10+ supports
   `fsutil file setCaseSensitiveInfo "<dir>" enable` (requires admin).
   Once enabled, the directory behaves like POSIX. galbum could detect
   this and use it when available, but the requirement to elevate makes
   it ill-suited for an automated tool.
3. **Manual handling** — document the collision in galbum output and
   leave it to the user to decide which version to keep.

`tools/place_loose_movs.py` currently uses `Path.hardlink_to` which raises
`WinError 183` on collision (Python's pathlib treats Windows
case-insensitivity correctly here). The script catches this and logs
the failure, but a smarter version would proactively detect existing
case-collisions before attempting placement.

**Galbum implications**: when scanning album folders, if two JSON
sidecars reference media files that case-collide, galbum should warn
that only one of the videos is accessible on Windows. The non-accessible
one's metadata can still be processed (galbum reads the JSON), but
writing EXIF won't reach the actual file because it doesn't exist on
disk under that name.

### 5. New manifest

Each export now starts with a tiny `takeout-<date>-001.zip` containing
only `Takeout/archive_browser.html` — a self-contained HTML inventory
of the export. Useful for users (browsable in any browser) but not
needed for galbum's pipeline.

## Code changes by module

### `galbum/json_matching.py` — biggest change

Today's `_stem_of_json()` strips `.json` and the `(N)` disambiguator.
The 5-step `find_json()` algorithm constructs candidates by appending
`.json`. Both need to learn the new suffix family.

**Recommended approach: index-by-title-first, fall back to filename pattern.**

```python
SUPPL_SUFFIXES = (
    ".supplemental-metadata.json",
    ".supplemental-metadat.json",
    ".supplemental-metada.json",
    ".supplemental-metad.json",
    ".supplemental-meta.json",
    ".json",  # old format + heavily-truncated new format
)


def _strip_json_suffix(name: str) -> Optional[str]:
    """Return the media filename a sidecar `name` describes, or None.
    Tries every known suffix variant in priority order."""
    for s in SUPPL_SUFFIXES:
        if name.endswith(s):
            return name[: -len(s)]
    return None
```

`build_json_index` should:
- Always read each JSON's `title` field and index by it (already does this — promote to primary)
- Continue indexing by exact filename for fast path

`find_json` should:
- Try title-based match first (covers full + truncated names + `(N)` variants)
- Fall back to filename pattern for the small set of edge cases title can't cover

The 5-step algorithm becomes simpler — most steps collapse into "look up by title with optional `(N)` adjustment."

### `galbum/metadata_parser.py` — small change

Two field changes:

1. `archived` field — new. Decide:
   - **Option A** (minimal): ignore it, only handle `favorited` as today
   - **Option B**: write a distinguishing tag (e.g. `XMP:Label="Archived"`) so archived photos can be filtered in viewers
   - **Recommended**: Option A for now (no spec yet for what an "archived" photo should look like in EXIF), revisit when user has a use case

2. `geoDataExif` rare — existing fallback logic still works (if absent, fall through to `geoData`). No code change needed.

### `galbum/scanner.py` — verify no English-album assumption

Check whether any path-construction or filename-pattern code assumes
English album folder names. Likely none — scanner walks all folders
generically — but worth a grep for `Photos from`, `Failed`, etc.

### `galbum/processor.py` — verify

Should be unaffected by format change (operates on already-parsed metadata).
Worth running existing e2e tests against new-format fixtures to verify.

### Tests / fixtures

Current fixtures in `tests/fixtures/e2e_album/` use the old `.json` suffix.

**Recommended:** add a NEW fixture directory `tests/fixtures/e2e_album_new_format/`
with a few canonical files using the new suffix variants:

- `IMG_0001.HEIC` + `IMG_0001.HEIC.supplemental-metadata.json` (full suffix)
- `LONG_FILENAME_THAT_GETS_TRUNCATED.HEIC` + `LONG_FILENAME_THAT_GETS_TRU.json`
  (heavily truncated — title field is authoritative)
- `IMG_0002.HEIC` + `IMG_0002.HEIC.supplemental-metadat.json` (one-char trim)
- album-level folder name in Chinese (e.g. `2024 年的相片/`)

Existing fixtures stay — backward-compat support for old format remains
valuable (some users have older exports).

### Loose-MOV placement (`tools/place_loose_movs.py` — already drafted)

Standalone tool, not part of galbum core. Run once after extraction to
copy split-out videos next to their album-folder sidecars. Implementation
lives in `tools/place_loose_movs.py`.

## Suggested PR sequence

Each PR independently shippable, no broken intermediate states:

1. **PR-A: `json_matching.py` suffix family + title-first matching**
   - Add `SUPPL_SUFFIXES` constant + `_strip_json_suffix` helper
   - Refactor `build_json_index` to index by title primarily
   - Refactor `find_json` to title-first, filename-pattern fallback
   - Add unit tests covering: full suffix, all 5 truncation variants,
     heavily-truncated (title-only-match) case, `(N)` disambiguator
   - All existing tests must continue to pass (old format still works)

2. **PR-B: e2e fixtures for new format**
   - New fixture dir `tests/fixtures/e2e_album_new_format/`
   - Mirror existing e2e tests to run against the new fixtures
   - Verify processor + metadata_parser handle the new format end-to-end

3. **PR-C: `archived` field handling (deferred)**
   - Skip until user has a concrete request for what to do with archived photos

4. **Standalone tool: `tools/place_loose_movs.py`** — already drafted, reviewable separately.

## Open questions (need user input)

- **Archived photos**: should they be flagged in EXIF / XMP somehow, or
  ignored? (Current proposal: ignore.)
- **Backward compat**: keep supporting old `.json` sidecar format in the
  same code path? (Current proposal: yes — minimal cost, helps anyone
  with mixed exports.)
- **Loose MOV placement**: copy or hardlink? (Hardlink saves disk but
  same-volume only; copy is robust to volume moves.)
- **e2e fixture set**: how many cases to cover for the new format? (Current
  proposal: 4–5 minimal canonical cases — full, one-char-trim, heavy-trim,
  `(N)`-dupe, Chinese-album-name.)

## Risks

- **Title-based matching can be fooled** if two media files in the same
  album folder share the exact same filename (one being a renamed copy
  of the other, with both JSONs claiming the same title). Mitigation:
  stay folder-scoped (don't try cross-folder title matches) and prefer
  exact filename match where available.
- **Truncated suffixes are not all enumerated**: I observed 5 variants in
  this sample. There may be more in larger exports (longer paths can
  produce shorter suffixes). Mitigation: make `_strip_json_suffix` use
  a regex `r'\.supplemental-(metadata|metadat|metada|metad|meta).json$'`
  rather than a hardcoded list — or even a regex that matches any prefix
  of "supplemental-metadata".
- **Heavily-truncated basenames** can collide. Two files
  `00100lrPORTRAIT_..._A.jpg` and `00100lrPORTRAIT_..._B.jpg` both
  truncated to `00100lrPORTRAIT_.json` would be indistinguishable by
  filename alone. The title field still distinguishes them. galbum must
  not rely on filename-only matching when truncation is in play.
