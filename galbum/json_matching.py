import json
from pathlib import Path
from typing import Optional

from .constants import COMPANION_PHOTO_EXTS, DUPE_RE
from .models import JsonIndex, MatchResult, MediaFile


# ---------------------------------------------------------------------------
# JSON index
# ---------------------------------------------------------------------------


def _stem_of_json(name: str) -> str:
    """Strip .json suffix, then strip everything after the last real extension."""
    without_json = name[: -len(".json")]   # "IMG_9556.HEIC(1)"
    # Base stem: strip trailing (N) if present
    m = DUPE_RE.match(Path(without_json).stem)
    return m.group(1) if m else Path(without_json).stem


def build_json_index(json_files: list) -> JsonIndex:
    by_exact = {}
    by_title = {}
    all_stems = {}

    for jp in json_files:
        by_exact[jp.name] = jp

        # Parse title field for UUID / truncation matching
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
            title = data.get("title", "")
            if title:
                by_title[title] = jp
        except Exception:
            pass

        stem = _stem_of_json(jp.name)
        all_stems.setdefault(stem, []).append(jp)

    return JsonIndex(by_exact=by_exact, by_title=by_title, all_stems=all_stems)


# ---------------------------------------------------------------------------
# JSON matching (5-step algorithm)
# ---------------------------------------------------------------------------


def find_json(mf: MediaFile, index: JsonIndex) -> Optional[MatchResult]:
    """Return the best-matching JSON path for this media file, or None."""

    # Step 1: Exact match  IMG_9556.HEIC -> IMG_9556.HEIC.json
    candidate = mf.path.name + ".json"
    if candidate in index.by_exact:
        return MatchResult(index.by_exact[candidate], "exact")

    # Step 2: Duplicate number reordering  IMG_9556(1).HEIC -> IMG_9556.HEIC(1).json
    if mf.number is not None:
        candidate = f"{mf.base_stem}{mf.suffix}({mf.number}).json"
        if candidate in index.by_exact:
            return MatchResult(index.by_exact[candidate], "duplicate")

    # Step 3: Live photo video orphan  IMG_9556(1).MP4 -> IMG_9556.HEIC(1).json
    if mf.suffix.upper() in (".MP4", ".MOV", ".M4V"):
        for photo_ext in COMPANION_PHOTO_EXTS:
            if mf.number is not None:
                candidate = f"{mf.base_stem}{photo_ext}({mf.number}).json"
            else:
                candidate = f"{mf.base_stem}{photo_ext}.json"
            if candidate in index.by_exact:
                return MatchResult(index.by_exact[candidate], "live_photo")

    # Step 4: Edited photo fallback  IMG_3818-已編輯.HEIC -> IMG_3818.HEIC.json
    if mf.is_edited:
        candidate = f"{mf.clean_stem}{mf.suffix}.json"
        if candidate in index.by_exact:
            return MatchResult(index.by_exact[candidate], "edited_fallback")
        if mf.number is not None:
            candidate = f"{mf.clean_stem}{mf.suffix}({mf.number}).json"
            if candidate in index.by_exact:
                return MatchResult(index.by_exact[candidate], "edited_fallback")

    # Step 5: Title-field match (handles UUID truncation in both directions)
    # e.g. media = "9A42C069-...-0000.mov", title = "9A42C069-...-00001E98C62951D8.mov"
    media_name = mf.path.name
    if len(mf.path.stem) > 10:
        for title, jp in index.by_title.items():
            short = min(len(media_name), len(title))
            # Both must share at least 80% of the shorter string as a common prefix
            threshold = int(short * 0.8)
            if threshold > 0 and media_name[:threshold] == title[:threshold]:
                return MatchResult(jp, "title_match")

    return None
