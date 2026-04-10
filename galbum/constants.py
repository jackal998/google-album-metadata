import re
from pathlib import Path

DEFAULT_ROOT = Path("D:/Downloads/Takeout/Google 相簿")
TEST_FOLDER_NAME = "測試"

MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".heic", ".png", ".gif", ".webp",
    ".tif", ".tiff", ".dng", ".cr2", ".nef", ".arw",
    ".mp4", ".mov", ".m4v", ".avi",
}

SKIP_FILENAMES = {"thumbs.db", "desktop.ini", "failed_inserting_exif.txt"}

# Chinese and English edited-photo suffixes to strip
EDITED_SUFFIXES = ["-已編輯", "(已編輯)", "-edited", "-Edit", "_edited", " edited"]

# Candidate photo extensions when looking up a video's companion image JSON
COMPANION_PHOTO_EXTS = [".HEIC", ".heic", ".JPG", ".jpg", ".JPEG", ".jpeg", ".PNG", ".png"]

# Duplicate number pattern:  "IMG_9556(1)"  ->  base="IMG_9556"  num=1
DUPE_RE = re.compile(r"^(.*)\((\d+)\)$")
