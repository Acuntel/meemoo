"""Fetch raw GMDCSA-24 + CaucaFall video clips (gitignored, curated subset).

Licensing verdict (research 05 §B.1): GMDCSA-24 is MIT and CaucaFall is
CC BY 4.0 — the ONLY two datasets cleared for bundling-derived-data in this
repo. Raw videos stay OUT of git (tests/fixtures/clips/raw/ is gitignored);
landmark JSONL extracted from them is what gets committed. Attribution lives
in tests/fixtures/landmarks/real/ATTRIBUTION.md.

URL history (2026-07-27): the original `main.zip` GitHub URL 404s (default
branch is `master`) and the Mendeley bulk `versions/4/download` endpoint was
retired. This script now pulls per-file: GMDCSA-24 via raw.githubusercontent
blobs, CaucaFall via the Mendeley public API (folders/{version} to map the
tree, then files?folder_id=... for each activity's .avi).

Usage:  uv run python -m tests.fixtures.clips.fetch [--dest tests/fixtures/clips/raw]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

GMDCSA_RAW = (
    "https://raw.githubusercontent.com/ekramalam/"
    "GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos/master"
)
CAUCA_API = "https://data.mendeley.com/public-api/datasets/7w7fccy7ky"
CAUCA_VERSION = 4
# Mendeley 403s the default urllib UA; any browser/curl-style UA passes.
UA = {"User-Agent": "meemoo-fixture-fetch/1.0 (+https://github.com/Acuntel/meemoo)"}

# Curated subset — fixture stem -> (subject, kind, file). Selection notes in
# tests/fixtures/labels/real_annotations.json (lighting, scenario coverage).
GMDCSA_CLIPS: dict[str, tuple[int, str, str]] = {
    "gm_s1_fall_05": (1, "Fall", "05.mp4"),
    "gm_s1_fall_11": (1, "Fall", "11.mp4"),
    "gm_s2_fall_01": (2, "Fall", "01.mp4"),
    "gm_s2_fall_10": (2, "Fall", "10.mp4"),  # night
    "gm_s2_fall_13": (2, "Fall", "13.mp4"),  # night
    "gm_s3_fall_05": (3, "Fall", "05.mp4"),  # slow collapse
    "gm_s3_fall_07": (3, "Fall", "07.mp4"),
    "gm_s3_fall_09": (3, "Fall", "09.mp4"),  # fall from floor-sitting
    "gm_s3_fall_16": (3, "Fall", "16.mp4"),  # night
    "gm_s3_fall_20": (3, "Fall", "20.mp4"),  # night
    "gm_s4_fall_03": (4, "Fall", "03.mp4"),  # lights off
    "gm_s4_fall_07": (4, "Fall", "07.mp4"),  # lights off
    "gm_s1_adl_01": (1, "ADL", "01.mp4"),  # sit -> sleep on bed
    "gm_s1_adl_04": (1, "ADL", "04.mp4"),  # sleeping -> sitting
    "gm_s2_adl_16": (2, "ADL", "16.mp4"),  # night: read -> sleep
    "gm_s2_adl_19": (2, "ADL", "19.mp4"),  # night: floor-sit writing
    "gm_s2_adl_22": (2, "ADL", "22.mp4"),  # push-ups
    "gm_s3_adl_08": (3, "ADL", "08.mp4"),  # deliberate lie-down on FLOOR
    "gm_s3_adl_09": (3, "ADL", "09.mp4"),  # floor -> sit -> stand (get up)
    "gm_s4_adl_02": (4, "ADL", "02.mp4"),  # walking, lights off
    "gm_s4_adl_10": (4, "ADL", "10.mp4"),  # walk -> sleep on bed
    "gm_s4_adl_15": (4, "ADL", "15.mp4"),  # sit -> sleep on bed
}

# fixture stem -> (subject number, activity folder name)
CAUCA_CLIPS: dict[str, tuple[int, str]] = {
    "cf_s1_fall_backwards": (1, "Fall backwards"),
    "cf_s1_fall_forward": (1, "Fall forward"),
    "cf_s1_fall_sitting": (1, "Fall sitting"),
    "cf_s1_walk": (1, "Walk"),
    "cf_s1_pickup": (1, "Pick up object"),
    "cf_s1_sit_down": (1, "Sit down"),
    "cf_s6_fall_forward": (6, "Fall forward"),  # 0 lux (IR)
    "cf_s6_fall_backwards": (6, "Fall backwards"),  # 0 lux (IR)
    "cf_s6_fall_left": (6, "Fall left"),  # 0 lux (IR)
    "cf_s6_walk": (6, "Walk"),  # 0 lux (IR)
    "cf_s6_kneel": (6, "Kneel"),  # 0 lux (IR)
    "cf_s8_fall_right": (8, "Fall right"),  # artificial ~125 lux
    "cf_s8_hop": (8, "Hop"),  # artificial ~125 lux
}

# License/metadata files kept beside the raw clips for the record.
GMDCSA_EXTRAS = ["LICENSE", "README.md"]


def _get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()  # type: ignore[no-any-return]


def _download(url: str, target: Path, label: str) -> bool:
    if target.exists() and target.stat().st_size > 0:
        print(f"{label}: already present")
        return True
    try:
        data = _get(url)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"{label}: FAILED ({exc}) url={url}", file=sys.stderr)
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    print(f"{label}: ok ({len(data) / 1e6:.1f} MB)")
    return True


def fetch_gmdcsa(dest: Path) -> bool:
    ok = True
    for extra in GMDCSA_EXTRAS:
        ok &= _download(f"{GMDCSA_RAW}/{extra}", dest / "gmdcsa24" / extra, f"gmdcsa24/{extra}")
    for subject in (1, 2, 3, 4):
        for kind in ("ADL", "Fall"):
            name = f"gmdcsa24/Subject{subject}_{kind}.csv"
            url = f"{GMDCSA_RAW}/Subject%20{subject}/{kind}.csv"
            ok &= _download(url, dest / "gmdcsa24" / f"Subject{subject}_{kind}.csv", name)
    for stem, (subject, kind, filename) in GMDCSA_CLIPS.items():
        url = f"{GMDCSA_RAW}/Subject%20{subject}/{kind}/{filename}"
        ok &= _download(url, dest / "gmdcsa24" / f"{stem}.mp4", f"gmdcsa24/{stem}")
    return ok


def _cauca_tree() -> tuple[dict[str, str], dict[str, str]]:
    """Folder tree -> ({folder_id: name}, {(subject.activity): folder_id})."""
    folders: list[dict[str, Any]] = json.loads(
        _get(f"{CAUCA_API}/folders/{CAUCA_VERSION}", timeout=60)
    )
    by_id = {f["id"]: f for f in folders}
    lookup: dict[str, str] = {}
    for f in folders:
        parent = by_id.get(f.get("parent_id") or "")
        if parent and parent["name"].startswith("Subject."):
            lookup[f"{parent['name']}/{f['name']}"] = f["id"]
    return {f["id"]: f["name"] for f in folders}, lookup


def _cauca_avi_url(folder_id: str) -> str | None:
    files: list[dict[str, Any]] = json.loads(
        _get(f"{CAUCA_API}/files?folder_id={folder_id}&version={CAUCA_VERSION}", timeout=60)
    )
    for f in files:
        if f["filename"].lower().endswith(".avi"):
            return str(f["content_details"]["download_url"])
    return None


def fetch_cauca(dest: Path) -> bool:
    try:
        _, lookup = _cauca_tree()
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        print(f"caucafall: folder listing FAILED ({exc})", file=sys.stderr)
        return False
    ok = True
    for stem, (subject, activity) in CAUCA_CLIPS.items():
        key = f"Subject.{subject}/{activity}"
        folder_id = lookup.get(key)
        if folder_id is None:
            print(f"caucafall/{stem}: no folder {key!r}", file=sys.stderr)
            ok = False
            continue
        target = dest / "caucafall" / f"{stem}.avi"
        if target.exists() and target.stat().st_size > 0:
            print(f"caucafall/{stem}: already present")
            continue
        try:
            url = _cauca_avi_url(folder_id)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            print(f"caucafall/{stem}: file listing FAILED ({exc})", file=sys.stderr)
            ok = False
            continue
        if url is None:
            print(f"caucafall/{stem}: no .avi in folder {key!r}", file=sys.stderr)
            ok = False
            continue
        ok &= _download(url, target, f"caucafall/{stem}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=Path(__file__).parent / "raw")
    args = parser.parse_args()
    args.dest.mkdir(parents=True, exist_ok=True)
    ok = fetch_gmdcsa(args.dest)
    ok = fetch_cauca(args.dest) and ok
    if not ok:
        print(
            "some downloads failed — landing pages:\n"
            "  https://github.com/ekramalam/GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos\n"
            "  https://data.mendeley.com/datasets/7w7fccy7ky/4",
            file=sys.stderr,
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
