import argparse
import logging
import subprocess
import sys
from pathlib import Path

from .constants import TEST_FOLDER_NAME
from .exiftool import ExiftoolProcess
from .metadata_parser import _TZ_FINDER
from .processor import process_folder
from .scanner import load_retry_files


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="galbum",
        description="Write Google Photos Takeout JSON metadata back into media files.",
    )
    sub = p.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # ------------------------------------------------------------------
    # galbum sync [path]
    # ------------------------------------------------------------------
    sync_p = sub.add_parser(
        "sync",
        help="Sync Takeout JSON metadata into media files.",
        description="Write Google Photos Takeout JSON metadata back into media files.",
    )
    sync_p.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=None,
        help="Root album folder (default: current directory)",
    )
    sync_p.add_argument("--folder", action="append", dest="folders",
                        help="Process only this subfolder name (repeatable)")
    sync_p.add_argument("--test-only", action="store_true",
                        help=f"Process only the {TEST_FOLDER_NAME!r} folder")
    sync_p.add_argument("--dry-run", action="store_true",
                        help="Preview operations without writing")
    sync_p.add_argument("--force", action="store_true",
                        help="Re-process files that already have DateTimeOriginal")
    sync_p.add_argument("--backup", action="store_true",
                        help="Keep exiftool _original backups (omits -overwrite_original)")
    sync_p.add_argument("--no-file-dates", action="store_true", dest="no_file_dates",
                        help="Do NOT update OS file creation/modification dates "
                             "(default: dates are set)")
    sync_p.add_argument("--exclude", action="append", dest="excludes", metavar="NAME",
                        help="Skip this subfolder name (repeatable)")
    sync_p.add_argument("--retry-failures", action="store_true", dest="retry_failures",
                        help="Re-process only files listed in failures.txt "
                             "(targeted retry, no full scan)")
    sync_p.add_argument("--log", type=Path, default=Path("galbum.log"),
                        help="Log file path (default: %(default)s)")
    return p


def parse_args():
    return _build_parser().parse_args()


def setup_logging(log_path: Path):
    fmt = "%(asctime)s %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    logging.basicConfig(
        level=logging.DEBUG,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    # Reduce console noise — only INFO+ to stdout
    logging.getLogger().handlers[1].setLevel(logging.INFO)


def check_exiftool() -> bool:
    if _TZ_FINDER:
        logging.info("timezonefinder active — timestamps will use local timezone from GPS")
    else:
        logging.info("timezonefinder not installed — timestamps will use UTC "
                     "(run: pip install timezonefinder to enable local timezone)")
    try:
        result = subprocess.run(["exiftool", "-ver"], capture_output=True, text=True)
        ver = result.stdout.strip()
        logging.info("exiftool version: %s", ver)
        return True
    except FileNotFoundError:
        print("ERROR: exiftool not found on PATH.")
        print("Install from https://exiftool.org/ and ensure it is in your PATH.")
        return False


def get_album_folders(root: Path, args) -> list:
    excludes = set(args.excludes or [])
    if args.test_only:
        return [root / TEST_FOLDER_NAME]
    if args.folders:
        return [root / name for name in args.folders if name not in excludes]
    return sorted(f for f in root.iterdir() if f.is_dir() and f.name not in excludes)


def _cmd_sync(args):
    root = (args.path or Path.cwd()).resolve()
    setup_logging(args.log)

    logging.info("=" * 60)
    logging.info("galbum starting. root=%s dry_run=%s force=%s",
                 root, args.dry_run, args.force)

    if not check_exiftool():
        sys.exit(1)

    # Output files (orphans.txt / failures.txt) land in the working directory
    cwd = Path.cwd()
    orphan_list = []
    fail_list = []

    with ExiftoolProcess() as et:
        if args.retry_failures:
            retry_map = load_retry_files(cwd / "failures.txt")
            if not retry_map:
                logging.info("No retryable files found. Exiting.")
                return
            logging.info("Retrying %d file(s) across %d folder(s)",
                         sum(len(v) for v in retry_map.values()), len(retry_map))
            for folder, file_set in sorted(retry_map.items()):
                process_folder(folder, args, et, logging.getLogger(), orphan_list, fail_list,
                               files_filter=file_set)
        else:
            folders = get_album_folders(root, args)
            missing = [f for f in folders if not f.exists()]
            if missing:
                for f in missing:
                    logging.error("Folder not found: %s", f)
                sys.exit(1)
            for folder in folders:
                process_folder(folder, args, et, logging.getLogger(), orphan_list, fail_list)

    if orphan_list:
        orphan_path = cwd / "orphans.txt"
        orphan_path.write_text("\n".join(orphan_list) + "\n", encoding="utf-8")
        logging.info("Orphan list written to: %s (%d files)", orphan_path, len(orphan_list))

    if fail_list:
        fail_path = cwd / "failures.txt"
        fail_path.write_text("\n".join(fail_list) + "\n", encoding="utf-8")
        logging.info("Failure list written to: %s (%d files)", fail_path, len(fail_list))

    logging.info("galbum done.")


def main():
    args = parse_args()
    if args.command == "sync":
        _cmd_sync(args)
