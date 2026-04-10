import logging
from pathlib import Path
from typing import Optional

from .exiftool import ExiftoolProcess, batch_read_processed, build_exiftool_args
from .file_type import _effective_path, get_file_type
from .filename_parser import parse_media_filename
from .json_matching import build_json_index, find_json
from .metadata_parser import parse_metadata
from .scanner import scan_folder


def process_folder(folder: Path, args, et: ExiftoolProcess, log, orphan_list: list, fail_list: list,
                   files_filter: Optional[set] = None):
    log.info("Processing folder: %s%s", folder.name,
             f" ({len(files_filter)} files)" if files_filter else "")
    media_files, json_files = scan_folder(folder)

    # When retrying, restrict to only the specified files
    if files_filter:
        media_files = [f for f in media_files if f in files_filter]

    if not media_files:
        log.info("  No media files found, skipping.")
        return

    index = build_json_index(json_files)

    # --retry-failures always force-processes; otherwise respect --force flag
    if files_filter or args.force:
        processed_set = set()
    else:
        processed_set = batch_read_processed(media_files, et)

    written = skipped = orphaned = failed = 0

    for path in media_files:
        mf = parse_media_filename(path)
        match = find_json(mf, index)

        if match is None:
            log.warning("[ORPH]  %s — no JSON match found", path.name)
            orphan_list.append(str(path))
            orphaned += 1
            continue

        metadata = parse_metadata(match.json_path)
        if metadata is None:
            log.warning("[FAIL]  %s — could not parse %s", path.name, match.json_path.name)
            fail_list.append(str(path))
            failed += 1
            continue

        if not args.force and path in processed_set:
            log.debug("[SKIP]  %s — already has DateTimeOriginal", path.name)
            skipped += 1
            continue

        gps_str = ""
        if metadata.gps:
            gps_str = f" gps={metadata.gps['latitude']:.4f},{metadata.gps['longitude']:.4f}"
        ts_str = f" ts={metadata.dt_str}" if metadata.dt_str else ""

        if args.dry_run:
            tag = match.match_type.upper()[:4]
            log.info("[DRY:%s] %s <- %s [%s]%s%s",
                     tag, path.name, match.json_path.name, match.match_type, ts_str, gps_str)
            written += 1
            continue

        file_type, needs_rename = get_file_type(path)
        if file_type == "skip":
            log.debug("[SKIP]  %s — unsupported type", path.name)
            skipped += 1
            continue

        with _effective_path(path, needs_rename, file_type) as effective:
            et_args = build_exiftool_args(effective, metadata, file_type,
                                           overwrite=not args.backup,
                                           set_file_dates=not args.no_file_dates)
            output = et.execute(et_args)

        label_map = {
            "exact": "OK",
            "duplicate": "DUPE",
            "live_photo": "LIVE",
            "edited_fallback": "EDIT",
            "title_match": "TITL",
        }
        label = label_map.get(match.match_type, match.match_type.upper())

        if "error" in output.lower() or "warning" in output.lower():
            # exiftool still exits 0 for warnings; check for real errors
            if "0 image files updated" in output and "error" in output.lower():
                log.error("[FAIL]  %s — exiftool: %s", path.name, output.strip())
                fail_list.append(str(path))
                failed += 1
                continue

        log.info("[%s]  %s <- %s [%s]%s%s",
                 label, path.name, match.json_path.name, match.match_type, ts_str, gps_str)
        written += 1

    action = "previewed" if args.dry_run else "written"
    print(f"[{folder.name}] {written} {action}, {skipped} skipped, {orphaned} orphan, {failed} failed")
    log.info("Folder %s complete: %d %s, %d skipped, %d orphan, %d failed",
             folder.name, written, action, skipped, orphaned, failed)
