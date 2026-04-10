import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Optional


def _magic_type(path: Path) -> Optional[str]:
    """Detect actual file type from magic bytes (first 12 bytes)."""
    try:
        header = path.read_bytes()[:12]
    except Exception:
        return None
    if header[:2] == b"\xff\xd8":
        return "jpeg"
    if header[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if header[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        brand = header[8:12].lower()
        if brand in (b"heic", b"heix", b"mif1", b"msf1", b"heim", b"heis"):
            return "heic"
        if brand in (b"mp41", b"mp42", b"isom", b"iso2", b"avc1", b"f4v ", b"m4v "):
            return "mp4"
        if brand in (b"qt  ",):
            return "mov"
    return None


_TYPE_TO_EXT = {
    "jpeg": ".jpg", "heic": ".heic", "raw": ".dng",
    "png": ".png", "gif": ".gif", "webp": ".webp",
    "mp4": ".mp4", "mov": ".mov",
}


def get_file_type(path: Path) -> tuple:
    """Return (file_type, needs_rename) where needs_rename is True if the file
    has a mismatched extension that requires a temp rename before exiftool."""
    ext = path.suffix.lower()
    ext_type_map = {
        ".jpg": "jpeg", ".jpeg": "jpeg",
        ".heic": "heic",
        ".dng": "raw", ".cr2": "raw", ".nef": "raw", ".arw": "raw",
        ".tif": "raw", ".tiff": "raw",
        ".png": "png",
        ".gif": "gif",
        ".webp": "webp",
        ".mp4": "mp4", ".m4v": "mp4",
        ".mov": "mov",
    }
    declared = ext_type_map.get(ext, "skip")

    # For image/container formats that can be misnamed (e.g. JPEG saved as .HEIC),
    # verify with magic bytes and return the actual type.
    if declared in ("heic", "raw", "png", "gif", "webp"):
        actual = _magic_type(path)
        if actual and actual != declared:
            logging.debug("Magic-byte mismatch: %s declared=%s actual=%s", path.name, declared, actual)
            return actual, True   # (type, needs_rename)

    return declared, False


@contextmanager
def _effective_path(path: Path, needs_rename: bool, actual_type: str):
    """If needs_rename, temporarily rename path to a correct extension, yield new path,
    then rename back. Otherwise yield path unchanged."""
    if not needs_rename:
        yield path
        return
    ext = _TYPE_TO_EXT.get(actual_type, path.suffix)
    temp_path = path.parent / (path.name + f".__fix{ext}")
    path.rename(temp_path)
    try:
        yield temp_path
    finally:
        # Rename back regardless of success/failure; temp file holds updated content
        if temp_path.exists():
            temp_path.rename(path)
