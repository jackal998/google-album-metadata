from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class MediaFile:
    path: Path
    base_stem: str          # stem with (N) stripped
    number: Optional[int]   # N from (N), or None
    suffix: str             # ".HEIC" (preserves original case)
    is_edited: bool
    clean_stem: str         # base_stem with edited suffix stripped


@dataclass
class ParsedMetadata:
    dt_str: str             # "YYYY:MM:DD HH:MM:SS+HH:MM" (local tz if GPS known, else UTC)
    gps: Optional[dict]     # raw geo dict, or None
    description: Optional[str]
    favorited: bool


@dataclass
class MatchResult:
    json_path: Path
    match_type: str         # exact | duplicate | live_photo | edited_fallback | title_match


@dataclass
class JsonIndex:
    by_exact: dict          # "IMG_9556.HEIC.json" -> Path
    by_title: dict          # json["title"] -> Path
    all_stems: dict         # "IMG_9556" -> [Path, ...]
