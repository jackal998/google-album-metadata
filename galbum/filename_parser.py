from pathlib import Path

from .constants import DUPE_RE, EDITED_SUFFIXES
from .models import MediaFile


def parse_media_filename(path: Path) -> MediaFile:
    """Decompose a media filename into its parts for JSON matching."""
    stem = path.stem          # "IMG_9556(1)"
    suffix = path.suffix      # ".HEIC"

    m = DUPE_RE.match(stem)
    if m:
        base_stem = m.group(1)
        number = int(m.group(2))
    else:
        base_stem = stem
        number = None

    is_edited = False
    clean_stem = base_stem
    for es in EDITED_SUFFIXES:
        if base_stem.endswith(es):
            clean_stem = base_stem[: -len(es)]
            is_edited = True
            break

    return MediaFile(
        path=path,
        base_stem=base_stem,
        number=number,
        suffix=suffix,
        is_edited=is_edited,
        clean_stem=clean_stem,
    )
