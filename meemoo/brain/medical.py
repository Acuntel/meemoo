"""Medical-question refusal-and-handoff rail — deterministic, before any LLM.

Constitution Art. IV §4: the LLM handles open conversation only, with
refusal-and-handoff rails for medical questions. This detector is pure
keyword/pattern matching (no model, no network) and runs in the engine BEFORE
any provider is consulted; on a hit the reply is a fixed template that hands
off to a human. Distress phrases ("help me") never reach here — the voice
pipeline's distress bypass fires first (Art. IV §5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Patterns that mark a medical question (recall-leaning; a false positive
#: costs one warm handoff sentence, a miss risks the robot playing doctor).
_MEDICAL_PATTERNS: tuple[str, ...] = (
    r"\b(double|skip|stop|change|increase|decrease)\b.{0,40}\b(dose|dosage|pill|pills|"
    r"medication|medicine|meds|insulin)\b",
    r"\b(dose|dosage|pill|pills|medication|medicine|meds|insulin)\b.{0,40}"
    r"\b(should i|can i|is it (ok|okay|safe)|how (much|many))\b",
    r"\b(should i|can i|is it (?:ok|okay|safe) to)\b.{0,40}\b(take|taking)\b.{0,40}"
    r"\b(pill|pills|medication|medicine|meds|aspirin|ibuprofen|tylenol|insulin)\b",
    r"\bdiagnos(e|is|ed)\b",
    r"\bis (this|it)\b.{0,30}\b(cancer|a stroke|a heart attack|infected|broken)\b",
    r"\bdo i have\b.{0,40}\b(cancer|dementia|diabetes|an infection|covid|pneumonia)\b",
    r"\bsymptom(s)? of\b",
    r"\bwhat does\b.{0,40}\b(blood pressure|blood sugar|heart rate|reading)\b"
    r".{0,20}\bmean\b",
    r"\bmy\b.{0,30}\b(blood pressure|blood sugar)\b.{0,30}\b(is|reads?|says?)\b"
    r".{0,20}\b(high|low|\d)",
    r"\bshould i (see|call|go to)\b.{0,30}\b(a )?(doctor|er|emergency room|hospital)\b",
    r"\bprescri(be|ption)\b",
)

_COMPILED = tuple(re.compile(p, re.IGNORECASE) for p in _MEDICAL_PATTERNS)

#: Deterministic handoff — never a model, never advice, always a person.
MEDICAL_HANDOFF = (
    "That's a really important question, and it's one for a person, not for me. "
    "I can't give medical advice. Your doctor or nurse can answer it properly, "
    "or we could ask your family to help. Would you like me to remind you to "
    "call them?"
)


@dataclass(frozen=True, slots=True)
class MedicalMatch:
    """Which pattern fired (logged; the reply is always the same template)."""

    pattern: str


class MedicalDetector:
    """Deterministic medical-question detector. No model in this path."""

    def check(self, text: str) -> MedicalMatch | None:
        for pattern in _COMPILED:
            if pattern.search(text):
                return MedicalMatch(pattern=pattern.pattern)
        return None
