import json
import re
from pathlib import Path
from typing import Optional

from .constants import COMPANION_PHOTO_EXTS, DUPE_RE
from .models import JsonIndex, MatchResult, MediaFile

# ---------------------------------------------------------------------------
# Suffix family
# ---------------------------------------------------------------------------
#
# Google Takeout exports created on/after May 2026 use
# ``<media>.<ext>.supplemental-metadata.json`` as the sidecar suffix. When
# the full path would exceed Windows MAX_PATH (260 chars), Google truncates
# the suffix from the right ("metadata" → "metadat" → "metada" …) and, in
# extreme cases, the basename too.
#
# When the same media file has duplicate uploads in Google Photos, the (N)
# disambiguator is placed *between* the suffix and ``.json``:
#     IMG_X.HEIC.supplemental-metadata(1).json
# (compared with the legacy form ``IMG_X.HEIC(1).json``). Our matcher's
# Step 2 candidate construction expects the (N) on the implied media name
# (``IMG_X.HEIC(1)``), so we strip the suffix and reattach (N) on the way
# out — this lets a single by_exact key serve both formats.
#
# Older exports (pre-May-2026) used a plain ``.json`` suffix. We continue
# to support that for users with mixed exports.

# Matches a new-format suffix: ``.supplemental-meta`` (with optional 1-4
# additional chars: ``meta``, ``metad``, ``metada``, ``metadat``,
# ``metadata``), an optional ``(N)`` disambiguator, and ``.json``. Anchored
# to the end of the string so we only match the trailing portion.
_SUPPL_FAMILY_RE = re.compile(
    r"\.supplemental-meta(?:data|dat|da|d)?(\(\d+\))?\.json$"
)

# Public list of suffix variants — kept for callers that want to know what
# we recognise. Listed longest-first; the dupe-disambiguator forms are
# implicit via _SUPPL_FAMILY_RE, not here.
SUPPL_SUFFIXES = (
    ".supplemental-metadata.json",
    ".supplemental-metadat.json",
    ".supplemental-metada.json",
    ".supplemental-metad.json",
    ".supplemental-meta.json",
    ".json",
)


def _strip_json_suffix(name: str) -> Optional[str]:
    """Return the implied media filename a sidecar `name` describes, or None.

    The implied name is what Step 1 / Step 2 / Step 3 / Step 4 candidate
    construction in ``find_json`` looks up. Notably, when the sidecar
    carries a ``(N)`` disambiguator we re-attach that ``(N)`` to the head
    so the result matches the ``IMG_X.HEIC(1)`` shape Step 2 produces for
    the corresponding ``IMG_X(1).HEIC`` media file.

    Examples — new format, no dupe:
        "IMG_0022.HEIC.supplemental-metadata.json" → "IMG_0022.HEIC"
        "IMG_X.HEIC.supplemental-metadat.json"     → "IMG_X.HEIC"

    Examples — new format, with dupe (the regression PR #7 missed):
        "IMG_X.HEIC.supplemental-metadata(1).json" → "IMG_X.HEIC(1)"
        "IMG_X.HEIC.supplemental-metad(1).json"    → "IMG_X.HEIC(1)"

    Examples — legacy format:
        "IMG_9556.HEIC.json"     → "IMG_9556.HEIC"
        "IMG_9556.HEIC(1).json"  → "IMG_9556.HEIC(1)"

    Heavily-truncated case (basename also trimmed by Google to fit
    MAX_PATH):
        "00100lrPORTRAIT_..._C(1).json" → "00100lrPORTRAIT_..._C(1)"
    The implied name in that case carries no extension and won't match a
    real media file by name — title-field matching (Step 5) handles it.
    """
    # New-format family first: matches both no-dupe and (N)-dupe forms in
    # one pass, including all five suffix-truncation variants.
    m = _SUPPL_FAMILY_RE.search(name)
    if m:
        head = name[: m.start()]
        dupe = m.group(1) or ""
        return head + dupe

    # Legacy ``.json`` form. The (N), when present, is already part of the
    # head (e.g. ``IMG_9556.HEIC(1)``), so plain truncation suffices.
    if name.endswith(".json"):
        return name[: -len(".json")]

    return None


# ---------------------------------------------------------------------------
# JSON index
# ---------------------------------------------------------------------------


def _stem_of_implied(implied: str) -> str:
    """From an implied-media-filename, return the base stem (extension stripped,
    trailing ``(N)`` stripped). Used to bucket sidecars by base for diagnostics
    or future fuzzy-match needs."""
    m = DUPE_RE.match(Path(implied).stem)
    return m.group(1) if m else Path(implied).stem


def build_json_index(json_files: list) -> JsonIndex:
    """Index a folder's JSON sidecars three ways:

      by_exact:  implied_media_filename → JSON path  (handles all suffix variants
                 uniformly — modern, legacy, and truncated forms collapse to the
                 same key when they describe the same media)
      by_title:  the JSON's own ``title`` field → JSON path  (authoritative when
                 the on-disk JSON name has been heavily truncated and the suffix
                 strip can't recover the original)
      all_stems: bare stem (no ext, no ``(N)``) → list of JSON paths  (kept for
                 future use; not required by find_json today)
    """
    by_exact: dict = {}
    by_title: dict = {}
    all_stems: dict = {}

    for jp in json_files:
        implied = _strip_json_suffix(jp.name)
        if implied:
            by_exact[implied] = jp
            all_stems.setdefault(_stem_of_implied(implied), []).append(jp)

        # Title field is the authoritative original media filename. Read it
        # for every JSON since heavily-truncated names rely on it.
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
            title = data.get("title")
            if isinstance(title, str) and title:
                by_title[title] = jp
        except Exception:  # noqa: BLE001 — corrupt JSONs are non-fatal
            pass

    return JsonIndex(by_exact=by_exact, by_title=by_title, all_stems=all_stems)


# ---------------------------------------------------------------------------
# JSON matching (5-step algorithm — keys are implied media filenames)
# ---------------------------------------------------------------------------


def find_json(mf: MediaFile, index: JsonIndex) -> Optional[MatchResult]:
    """Return the best-matching JSON path for this media file, or None.

    The index keys are *implied media filenames* (suffix already stripped),
    so candidate construction here just builds the media-filename form —
    no ``.json`` appended. This makes a single lookup work for every
    sidecar suffix variant uniformly.
    """

    # Step 1: Exact match  IMG_9556.HEIC -> implied key IMG_9556.HEIC
    if mf.path.name in index.by_exact:
        return MatchResult(index.by_exact[mf.path.name], "exact")

    # Step 2: Duplicate number reordering  IMG_9556(1).HEIC -> IMG_9556.HEIC(1)
    if mf.number is not None:
        candidate = f"{mf.base_stem}{mf.suffix}({mf.number})"
        if candidate in index.by_exact:
            return MatchResult(index.by_exact[candidate], "duplicate")

    # Step 3: Live photo video orphan  IMG_9556(1).MP4 -> IMG_9556.HEIC(1)
    if mf.suffix.upper() in (".MP4", ".MOV", ".M4V"):
        for photo_ext in COMPANION_PHOTO_EXTS:
            if mf.number is not None:
                candidate = f"{mf.base_stem}{photo_ext}({mf.number})"
            else:
                candidate = f"{mf.base_stem}{photo_ext}"
            if candidate in index.by_exact:
                return MatchResult(index.by_exact[candidate], "live_photo")

    # Step 4: Edited photo fallback  IMG_3818-已編輯.HEIC -> IMG_3818.HEIC
    if mf.is_edited:
        candidate = f"{mf.clean_stem}{mf.suffix}"
        if candidate in index.by_exact:
            return MatchResult(index.by_exact[candidate], "edited_fallback")
        if mf.number is not None:
            candidate = f"{mf.clean_stem}{mf.suffix}({mf.number})"
            if candidate in index.by_exact:
                return MatchResult(index.by_exact[candidate], "edited_fallback")

    # Step 5: Title-field match (handles UUID truncation and heavily-truncated
    # JSON filenames whose suffix-stripped form lacks the original extension)
    media_name = mf.path.name
    if len(mf.path.stem) > 10:
        for title, jp in index.by_title.items():
            short = min(len(media_name), len(title))
            # Both must share at least 80% of the shorter string as a common prefix
            threshold = int(short * 0.8)
            if threshold > 0 and media_name[:threshold] == title[:threshold]:
                return MatchResult(jp, "title_match")

    return None
