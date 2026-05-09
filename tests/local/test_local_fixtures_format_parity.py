"""
Opt-in tests that run galbum's pipeline against real Google Takeout data
preserved in `.local-fixtures/` (gitignored), in BOTH the old `.json` and
the new `.supplemental-metadata.json` sidecar formats.

Purpose: regression-seal the invariant that old- and new-format Takeout
exports of the same underlying photo produce IDENTICAL galbum output
(same `dt_str`, same `gps`, same `favorited`). Synthetic fixtures alone
can't catch divergences in the schema or matcher when Google changes
something subtle between exports — this hits real bytes from real exports.

How to run:
    pytest -m local_fixtures

The whole suite is auto-skipped when `.local-fixtures/` doesn't exist on
the machine (i.e. always skipped in CI; only runs locally for the user
who has these private fixtures preserved).

Layout expected at repo root:

    .local-fixtures/
        tier-2-offset-original/
            old-format/{IMG_0022.HEIC, IMG_0022.HEIC.json}
            new-format/{IMG_0022.HEIC, IMG_0022.HEIC.supplemental-metadata.json}
        tier-3-iptc-inference/
            old-format/{748877600.799807.jpg, .json}
            new-format/{748877600.799807.jpg, .supplemental-metadata.json}
        tier-4-no-signal/
            old-format/{IMG_3076.JPG, .json}
            new-format/{IMG_3076.JPG, .supplemental-metadata.json}
        multi-album-sameness/
            old-format/{takeout-Nishi-Nihon, takeout-Osaka42, takeout-Photos-from-2024}/
            new-format/{takeout-Nishi-Nihon, takeout-Osaka42, takeout-2024nian}/

Media bytes typically DIFFER across formats (Google re-encodes between
exports), so the assertion is on parsed-metadata equivalence, not byte
equivalence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from galbum import ExiftoolProcess, batch_read_processed
from galbum.json_matching import build_json_index, find_json
from galbum.filename_parser import parse_media_filename
from galbum.metadata_parser import parse_metadata


_LOCAL_FIXTURES = Path(__file__).resolve().parents[2] / ".local-fixtures"

# Skip the whole module if the local-only fixtures aren't present
pytestmark = [
    pytest.mark.local_fixtures,
    pytest.mark.skipif(
        not _LOCAL_FIXTURES.is_dir(),
        reason=f".local-fixtures/ not present at {_LOCAL_FIXTURES} — skipping local-only tests",
    ),
]


# ---------------------------------------------------------------------------
# Helper: evaluate one folder through the full pipeline
# ---------------------------------------------------------------------------

def _evaluate(folder: Path, et: ExiftoolProcess) -> dict:
    """Match the first media file in `folder` to its sidecar JSON and return
    the parsed metadata fields that callers care about."""
    media = sorted(p for p in folder.iterdir()
                   if p.is_file()
                   and p.suffix.lower() in (".heic", ".jpg", ".jpeg", ".png", ".dng",
                                             ".mov", ".mp4"))
    jsons = sorted(p for p in folder.iterdir() if p.suffix == ".json")
    assert media, f"no media file in {folder}"
    assert jsons, f"no JSON sidecar in {folder}"

    index = build_json_index(jsons)
    media_file = media[0]
    mf = parse_media_filename(media_file)
    match = find_json(mf, index)
    assert match is not None, f"no JSON match for {media_file.name} in {folder}"

    _, offsets, naives = batch_read_processed([media_file], et)
    meta = parse_metadata(
        match.json_path,
        existing_offset=offsets.get(media_file),
        existing_local_naive=naives.get(media_file),
    )
    assert meta is not None, f"parse_metadata returned None for {match.json_path}"

    return {
        "media": media_file.name,
        "json": match.json_path.name,
        "match_type": match.match_type,
        "dt_str": meta.dt_str,
        "gps": meta.gps,
        "favorited": meta.favorited,
    }


@pytest.fixture(scope="module")
def et():
    """One ExiftoolProcess shared across the module — startup is the slow part."""
    with ExiftoolProcess() as proc:
        yield proc


# ---------------------------------------------------------------------------
# Format parity per recovery tier
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case_dir", [
    "tier-2-offset-original",
    "tier-3-iptc-inference",
    "tier-4-no-signal",
])
def test_old_and_new_format_produce_same_metadata(case_dir, et):
    """For each tier case, the old (.json) and new (.supplemental-metadata.json)
    sidecars of the same source photo must produce identical parsed metadata.

    Bytes of the media file may differ (Google re-encodes between exports);
    that's expected and fine. What MUST match: dt_str, gps, favorited.
    """
    base = _LOCAL_FIXTURES / case_dir
    if not (base / "old-format").is_dir() or not (base / "new-format").is_dir():
        pytest.skip(f"{case_dir} missing old-format/ or new-format/ subdir")

    old = _evaluate(base / "old-format", et)
    new = _evaluate(base / "new-format", et)

    assert old["dt_str"] == new["dt_str"], \
        f"{case_dir}: dt_str diverged\n  old: {old}\n  new: {new}"
    assert old["gps"] == new["gps"], f"{case_dir}: gps diverged"
    assert old["favorited"] == new["favorited"], f"{case_dir}: favorited diverged"
    assert old["match_type"] == new["match_type"], \
        f"{case_dir}: match_type diverged ({old['match_type']!r} vs {new['match_type']!r})"


# ---------------------------------------------------------------------------
# Multi-album sameness: same shot in N albums should produce same dt_str
# in both formats, across every album the photo is in
# ---------------------------------------------------------------------------

# Map old-format album dir → new-format album dir. The user-facing album
# name "Photos from 2024" was localised to "2024 年的相片" in the new export;
# our local-fixtures use "takeout-2024nian" for the new variant.
_MULTI_ALBUM_MAPPING = {
    "takeout-Nishi-Nihon": "takeout-Nishi-Nihon",
    "takeout-Osaka42": "takeout-Osaka42",
    "takeout-Photos-from-2024": "takeout-2024nian",
}


@pytest.mark.parametrize("old_album,new_album", list(_MULTI_ALBUM_MAPPING.items()))
def test_multi_album_sameness(old_album, new_album, et):
    """The same source photo (IMG_3152.DNG taken in Kyoto) appears in three
    different Takeout albums. galbum should produce the same dt_str for it
    regardless of which album's sidecar is read, in both old and new formats.
    """
    base = _LOCAL_FIXTURES / "multi-album-sameness"
    old = base / "old-format" / old_album
    new = base / "new-format" / new_album

    if not old.is_dir() or not new.is_dir():
        pytest.skip(f"{old_album} or {new_album} missing")

    old_meta = _evaluate(old, et)
    new_meta = _evaluate(new, et)

    assert old_meta["dt_str"] == new_meta["dt_str"], \
        f"{old_album} vs {new_album}: dt_str diverged"


def test_multi_album_old_format_dt_str_consistent_across_albums(et):
    """Sanity within one format: the three old-format albums should agree
    on dt_str (since they all reference the same source photo)."""
    base = _LOCAL_FIXTURES / "multi-album-sameness" / "old-format"
    if not base.is_dir():
        pytest.skip("old-format multi-album not present")
    results = []
    for album in _MULTI_ALBUM_MAPPING:
        d = base / album
        if d.is_dir():
            results.append((album, _evaluate(d, et)["dt_str"]))
    dt_strs = {dt for _, dt in results}
    assert len(dt_strs) == 1, \
        f"old-format albums disagree on dt_str: {results}"


def test_multi_album_new_format_dt_str_consistent_across_albums(et):
    """Same sanity check but for the new-format multi-album set."""
    base = _LOCAL_FIXTURES / "multi-album-sameness" / "new-format"
    if not base.is_dir():
        pytest.skip("new-format multi-album not present")
    results = []
    for new_album in _MULTI_ALBUM_MAPPING.values():
        d = base / new_album
        if d.is_dir():
            results.append((new_album, _evaluate(d, et)["dt_str"]))
    dt_strs = {dt for _, dt in results}
    assert len(dt_strs) == 1, \
        f"new-format albums disagree on dt_str: {results}"
