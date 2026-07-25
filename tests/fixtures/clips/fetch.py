"""Fetch the raw GMDCSA-24 + CaucaFall video clips (gitignored, ~0.5 GB).

Licensing verdict (research 05 §B.1): GMDCSA-24 is MIT/CC BY and CaucaFall is
CC BY 4.0 — the ONLY two datasets cleared for bundling-derived-data in this
repo. Raw videos stay out of git; landmark JSONL extracted from them is what
gets committed (tests/fixtures/extract_landmarks.py).

Usage:  uv run python -m tests.fixtures.clips.fetch [--dest tests/fixtures/clips]
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

SOURCES: dict[str, dict[str, str]] = {
    "gmdcsa24": {
        # MIT-licensed repo; videos linked from the README (Google Drive).
        "url": "https://github.com/ekramalam/GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos/archive/refs/heads/main.zip",
        "filename": "gmdcsa24-main.zip",
        "landing": "https://github.com/ekramalam/GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos",
    },
    "caucafall": {
        # CC BY 4.0, Mendeley Data v4 archive download.
        "url": "https://data.mendeley.com/public-files/datasets/7w7fccy7ky/versions/4/download",
        "filename": "caucafall-v4.zip",
        "landing": "https://data.mendeley.com/datasets/7w7fccy7ky/4",
    },
}


def fetch(name: str, dest: Path) -> bool:
    src = SOURCES[name]
    target = dest / src["filename"]
    if target.exists():
        print(f"{name}: already present at {target}")
        return True
    print(f"{name}: downloading {src['url']} -> {target}")
    try:
        with urllib.request.urlopen(src["url"], timeout=120) as resp:  # noqa: S310
            target.write_bytes(resp.read())
        print(f"{name}: done ({target.stat().st_size / 1e6:.1f} MB)")
        return True
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(
            f"{name}: automated download failed ({exc}).\n"
            f"  Fetch manually from {src['landing']} and save as {target}",
            file=sys.stderr,
        )
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    args.dest.mkdir(parents=True, exist_ok=True)
    ok = all([fetch("gmdcsa24", args.dest), fetch("caucafall", args.dest)])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
