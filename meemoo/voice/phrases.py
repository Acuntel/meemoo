"""Fuzzy phrase matching for the safety detectors — pure stdlib, no network.

Constitution Art. IV §4: no generative model in the safety path. This module
is deliberately boring: normalization + token-level Levenshtein over a fixed
phrase list. It must import nothing that could ever touch the network, a model
file, or an API key — reviewers should be able to read this file top to bottom
and see exactly what fires an escalation.

Tuning is recall-over-precision (Art. IV §5): a false alarm costs a cheap
question ("did you need help?"); a miss is the catastrophe. STT typos like
"helb me" or "emergensee" must still land.
"""

from __future__ import annotations

from dataclasses import dataclass

_PUNCT = str.maketrans({c: " " for c in ",.;:!?\"'()[]-—…"})

# Tokens shorter than this must match exactly; longer ones get 1 edit of slack.
_FUZZY_MIN_LEN = 4
_MAX_EDITS = 1


def normalize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split into tokens."""
    return text.lower().translate(_PUNCT).split()


def levenshtein_at_most_1(a: str, b: str) -> bool:
    """True if edit distance(a, b) ≤ 1 — O(len) two-pointer, no DP table."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la > lb:  # ensure a is the shorter
        a, b, la, lb = b, a, lb, la
    i = j = 0
    edited = False
    while i < la and j < lb:
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        if edited:
            return False
        edited = True
        if la == lb:  # substitution
            i += 1
        j += 1  # insertion into a / deletion from b
    return True


def _token_matches(heard: str, target: str) -> bool:
    if heard == target:
        return True
    if len(target) < _FUZZY_MIN_LEN:
        return False  # short words: exact only ("me", "i", "911")
    return levenshtein_at_most_1(heard, target)


@dataclass(frozen=True, slots=True)
class PhraseMatch:
    """A phrase hit: which configured phrase, and the tokens that matched it."""

    phrase: str
    matched_text: str


class PhraseMatcher:
    """Match any of a fixed phrase list inside an utterance, fuzzily.

    A phrase matches if its tokens appear as a contiguous token window of the
    utterance, each token exact or (for tokens ≥ 4 chars) within edit
    distance 1. "please help me now" ⇒ matches "help me".
    """

    def __init__(self, phrases: tuple[str, ...]) -> None:
        if not phrases:
            raise ValueError("PhraseMatcher needs at least one phrase")
        self._phrases: list[tuple[str, list[str]]] = [(p, normalize(p)) for p in phrases]
        for phrase, tokens in self._phrases:
            if not tokens:
                raise ValueError(f"phrase {phrase!r} normalizes to nothing")

    def match(self, text: str) -> PhraseMatch | None:
        """First matching phrase in ``text``, or ``None``."""
        heard = normalize(text)
        if not heard:
            return None
        for phrase, targets in self._phrases:
            n = len(targets)
            for start in range(0, len(heard) - n + 1):
                window = heard[start : start + n]
                if all(_token_matches(w, t) for w, t in zip(window, targets, strict=True)):
                    return PhraseMatch(phrase=phrase, matched_text=" ".join(window))
        return None
