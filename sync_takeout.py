#!/usr/bin/env python3
"""
sync_takeout.py — Compatibility shim. All logic lives in the galbum package.

Usage:
  python sync_takeout.py --dry-run       # preview operations
  python sync_takeout.py                 # process all albums
  python -m galbum                       # preferred invocation via package
"""
from galbum import (  # noqa: F401  (re-exported for test imports)
    COMPANION_PHOTO_EXTS,
    DEFAULT_ROOT,
    DUPE_RE,
    EDITED_SUFFIXES,
    MEDIA_EXTENSIONS,
    SKIP_FILENAMES,
    TEST_FOLDER_NAME,
    ExiftoolProcess,
    JsonIndex,
    MatchResult,
    MediaFile,
    ParsedMetadata,
    _effective_path,
    _local_datetime,
    _magic_type,
    batch_read_processed,
    build_exiftool_args,
    build_json_index,
    find_json,
    get_file_type,
    is_valid_gps,
    load_retry_files,
    main,
    parse_media_filename,
    parse_metadata,
    process_folder,
    scan_folder,
)

if __name__ == "__main__":
    main()
