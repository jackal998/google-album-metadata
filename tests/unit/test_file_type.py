"""
Unit tests for get_file_type() and _magic_type().

Magic-byte tests write tiny byte sequences to tmp_path to simulate real files.
"""

import struct
from pathlib import Path

import pytest

from galbum import _magic_type, get_file_type


# ---------------------------------------------------------------------------
# Helpers: write files with specific magic bytes
# ---------------------------------------------------------------------------

def write_jpeg(path: Path) -> Path:
    path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 8)
    return path

def write_png(path: Path) -> Path:
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 4)
    return path

def write_heic(path: Path) -> Path:
    # ftyp box: size(4) + "ftyp"(4) + "heic"(4)
    path.write_bytes(b"\x00\x00\x00\x14ftyp" + b"heic" + b"\x00" * 8)
    return path

def write_mp4_isom(path: Path) -> Path:
    path.write_bytes(b"\x00\x00\x00\x14ftyp" + b"isom" + b"\x00" * 8)
    return path

def write_mov(path: Path) -> Path:
    path.write_bytes(b"\x00\x00\x00\x14ftyp" + b"qt  " + b"\x00" * 8)
    return path

def write_gif(path: Path) -> Path:
    path.write_bytes(b"GIF89a" + b"\x00" * 6)
    return path

def write_webp(path: Path) -> Path:
    path.write_bytes(b"RIFF\x00\x00\x00\x00WEBP")
    return path

def write_garbage(path: Path) -> Path:
    path.write_bytes(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b")
    return path


# ---------------------------------------------------------------------------
# _magic_type
# ---------------------------------------------------------------------------

class TestMagicType:
    def test_jpeg_magic(self, tmp_path):
        assert _magic_type(write_jpeg(tmp_path / "f.jpg")) == "jpeg"

    def test_png_magic(self, tmp_path):
        assert _magic_type(write_png(tmp_path / "f.png")) == "png"

    def test_heic_magic(self, tmp_path):
        assert _magic_type(write_heic(tmp_path / "f.heic")) == "heic"

    def test_mp4_isom_magic(self, tmp_path):
        assert _magic_type(write_mp4_isom(tmp_path / "f.mp4")) == "mp4"

    def test_mov_magic(self, tmp_path):
        assert _magic_type(write_mov(tmp_path / "f.mov")) == "mov"

    def test_gif_magic(self, tmp_path):
        assert _magic_type(write_gif(tmp_path / "f.gif")) == "gif"

    def test_webp_magic(self, tmp_path):
        assert _magic_type(write_webp(tmp_path / "f.webp")) == "webp"

    def test_unknown_bytes_returns_none(self, tmp_path):
        assert _magic_type(write_garbage(tmp_path / "f.bin")) is None

    def test_missing_file_returns_none(self, tmp_path):
        assert _magic_type(tmp_path / "nonexistent.jpg") is None


# ---------------------------------------------------------------------------
# get_file_type — extension-based (no magic mismatch)
# ---------------------------------------------------------------------------

class TestGetFileTypeByExtension:
    @pytest.mark.parametrize("name,expected_type", [
        ("photo.jpg",  "jpeg"),
        ("photo.jpeg", "jpeg"),
        ("photo.HEIC", "heic"),
        ("photo.dng",  "raw"),
        ("photo.CR2",  "raw"),
        ("photo.nef",  "raw"),
        ("photo.arw",  "raw"),
        ("photo.tif",  "raw"),
        ("photo.tiff", "raw"),
        ("photo.gif",  "gif"),
        ("photo.webp", "webp"),
        ("photo.mp4",  "mp4"),
        ("photo.m4v",  "mp4"),
        ("photo.mov",  "mov"),
        ("photo.txt",  "skip"),
        ("photo.json", "skip"),
        ("Thumbs.db",  "skip"),
    ])
    def test_extension_mapping(self, tmp_path, name, expected_type):
        # Create a minimal valid file so magic-byte check doesn't explode
        f = tmp_path / name
        # For image types, write proper magic bytes so they don't trigger mismatch
        if expected_type == "jpeg":
            write_jpeg(f)
        elif expected_type == "gif":
            write_gif(f)
        elif expected_type == "webp":
            write_webp(f)
        else:
            f.write_bytes(b"\x00" * 12)

        file_type, needs_rename = get_file_type(f)
        assert file_type == expected_type

    @pytest.mark.parametrize("name", ["photo.jpg", "photo.jpeg"])
    def test_jpeg_no_rename_needed(self, tmp_path, name):
        f = tmp_path / name
        write_jpeg(f)
        _, needs_rename = get_file_type(f)
        assert needs_rename is False


# ---------------------------------------------------------------------------
# get_file_type — magic-byte mismatch (needs_rename=True)
# ---------------------------------------------------------------------------

class TestGetFileTypeMismatch:
    def test_heic_that_is_actually_jpeg(self, tmp_path):
        # File has .HEIC extension but JPEG magic bytes
        f = tmp_path / "photo.HEIC"
        write_jpeg(f)
        file_type, needs_rename = get_file_type(f)
        assert file_type == "jpeg"
        assert needs_rename is True

    def test_png_that_is_actually_jpeg(self, tmp_path):
        f = tmp_path / "photo.png"
        write_jpeg(f)
        file_type, needs_rename = get_file_type(f)
        assert file_type == "jpeg"
        assert needs_rename is True

    def test_gif_that_is_actually_png(self, tmp_path):
        f = tmp_path / "photo.gif"
        write_png(f)
        file_type, needs_rename = get_file_type(f)
        assert file_type == "png"
        assert needs_rename is True

    def test_correct_heic_no_rename(self, tmp_path):
        f = tmp_path / "photo.heic"
        write_heic(f)
        file_type, needs_rename = get_file_type(f)
        assert file_type == "heic"
        assert needs_rename is False
