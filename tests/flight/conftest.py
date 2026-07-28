"""Shared flight-test helpers.

The canonical randomized docking episode lives in
``meemoo.flight.dock_bench`` (the same runner the Monte-Carlo bench uses, so
tests and the published gate numbers can never drift apart). Re-exported
here because every flight test imports it from this module.
"""

from __future__ import annotations

from meemoo.flight.dock_bench import EpisodeResult, run_episode

__all__ = ["EpisodeResult", "run_episode"]
