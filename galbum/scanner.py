import logging
from pathlib import Path

from .constants import MEDIA_EXTENSIONS, SKIP_FILENAMES


def load_retry_files(failures_path: Path) -> dict:
    """Read failures.txt and return {folder_path: {file_path, ...}} for targeted retry."""
    folder_map = {}
    if not failures_path.exists():
        logging.error("failures.txt not found at %s", failures_path)
        return folder_map
    for line in failures_path.read_text(encoding="utf-8").splitlines():
        p = Path(line.strip())
        if p.exists():
            folder_map.setdefault(p.parent, set()).add(p)
        else:
            logging.warning("Retry file not found on disk: %s", p)
    return folder_map


def scan_folder(folder: Path) -> tuple:
    """Return (media_files, json_files) for a folder (non-recursive)."""
    media_files = []
    json_files = []
    for f in sorted(folder.iterdir()):
        if not f.is_file():
            continue
        if f.name.lower() in SKIP_FILENAMES:
            continue
        if f.suffix.lower() == ".json":
            json_files.append(f)
        elif f.suffix.lower() in MEDIA_EXTENSIONS:
            media_files.append(f)
    return media_files, json_files
