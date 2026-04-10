#!/usr/bin/env python3
"""
sync_takeout.py — Compatibility shim. All logic lives in the galbum package.

Preferred usage:
  galbum sync [path]           # installed CLI command
  python -m galbum sync [path] # module invocation

Legacy usage (still works):
  python sync_takeout.py sync [path]
"""
from galbum import (  # noqa: F401  (re-exported for backwards compatibility)
    COMPANION_PHOTO_EXTS,
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
