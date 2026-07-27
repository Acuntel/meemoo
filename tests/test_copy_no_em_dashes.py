"""Amendment A7: no em dashes anywhere in product copy.

The Phase-7.5 copy sweep covered the web bundle and the API-served strings.
This is the backstop for the copy nobody greps: the lines Meemoo SAYS, and
the text a hosted model generates into a transcript the family reads.

Engineering output is deliberately out of scope. Log messages, exception
text, comments and docstrings are for us, not for the resident, and they keep
their dashes.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from meemoo.brain.medical import MEDICAL_HANDOFF
from meemoo.brain.paraphrase import BANKS
from meemoo.brain.personality import BASE_TEMPLATE, plain_dashes
from meemoo.brain.scripted import CONCERN_REPLY, OK_REPLY, UNSURE_REPLY
from meemoo.guardian.escalation import CALL_TEMPLATE, SMS_TEMPLATE
from meemoo.guardian.service import CHECKIN_GREETING, VERIFY_PROMPT
from meemoo.voice.crisis import CRISIS_RESPONSE
from meemoo.voice.disclosure import DISCLOSURE_LINE, REALNESS_ANSWER, REDISCLOSURE_LINE
from meemoo.voice.distress import DISTRESS_ACK
from meemoo.voice.motion import DIRECTION_LINES, STOP_LINE

REPO = pathlib.Path(__file__).resolve().parents[1]

#: Every fixed line Meemoo speaks aloud or sends to a family member.
SPOKEN_COPY: dict[str, str] = {
    "DISTRESS_ACK": DISTRESS_ACK,
    "CRISIS_RESPONSE": CRISIS_RESPONSE,
    "MEDICAL_HANDOFF": MEDICAL_HANDOFF,
    "DISCLOSURE_LINE": DISCLOSURE_LINE,
    "REDISCLOSURE_LINE": REDISCLOSURE_LINE,
    "REALNESS_ANSWER": REALNESS_ANSWER,
    "CHECKIN_GREETING": CHECKIN_GREETING,
    "VERIFY_PROMPT": VERIFY_PROMPT,
    "CONCERN_REPLY": CONCERN_REPLY,
    "OK_REPLY": OK_REPLY,
    "UNSURE_REPLY": UNSURE_REPLY,
    "SMS_TEMPLATE": SMS_TEMPLATE,
    "CALL_TEMPLATE": CALL_TEMPLATE,
    "STOP_LINE": STOP_LINE,
    **{f"DIRECTION_LINES[{k}]": v for k, v in DIRECTION_LINES.items()},
}


@pytest.mark.parametrize(("name", "line"), sorted(SPOKEN_COPY.items()))
def test_spoken_line_has_no_em_dash(name: str, line: str) -> None:
    assert "—" not in line and "–" not in line, name


def test_paraphrase_bank_has_no_em_dashes() -> None:
    """Every greeting, praise and reminder variant, not just the ones in use."""
    for kind, variants in BANKS.items():
        for line in variants:
            assert "—" not in line, f"{kind}: {line}"


def test_the_prompt_forbids_dashes_and_uses_none() -> None:
    """The model writes most of the copy, so the rule lives in the prompt."""
    assert "—" not in BASE_TEMPLATE
    assert "Never use a dash to join clauses" in BASE_TEMPLATE


class TestSanitizer:
    """Enforcement, not a promise: generated replies are rewritten (A7)."""

    @pytest.mark.parametrize(
        ("raw", "clean"),
        [
            ("I'm fine — how are you?", "I'm fine, how are you?"),
            ("wait—what?", "wait, what?"),
            ("no dashes here", "no dashes here"),
            ("a range of 3–4 days", "a range of 3-4 days"),
        ],
    )
    def test_dashes_are_rewritten(self, raw: str, clean: str) -> None:
        assert plain_dashes(raw) == clean

    def test_output_is_always_clean(self) -> None:
        for raw in ["a — b", "a—b", "a – b", "a–b", "—", "start—", "—end"]:
            assert "—" not in plain_dashes(raw) and "–" not in plain_dashes(raw)


def test_no_em_dashes_in_the_web_bundle() -> None:
    """A7 again, for the consumer surface (the sibling agent's sweep)."""
    offenders = [
        f"{path.relative_to(REPO)}"
        for path in (REPO / "web" / "src").rglob("*")
        if path.suffix in {".ts", ".tsx", ".css", ".html"}
        and "—" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_no_em_dashes_in_user_facing_python_literals() -> None:
    """Catches a new spoken string that skips the registry above.

    Only modules whose strings reach a person are scanned; a log line in
    ``runtime.py`` is engineering output and keeps its dash.
    """
    user_facing = [
        "meemoo/voice/distress.py", "meemoo/voice/crisis.py",
        "meemoo/voice/disclosure.py", "meemoo/voice/motion.py",
        "meemoo/brain/medical.py", "meemoo/brain/scripted.py",
        "meemoo/brain/paraphrase.py", "meemoo/brain/personality.py",
        "meemoo/flight/capabilities.py",
    ]
    offenders: list[str] = []
    for name in user_facing:
        tree = ast.parse((REPO / name).read_text(encoding="utf-8"))
        skip = _engineering_strings(tree)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and "—" in node.value
                and id(node) not in skip
                and node.value not in _ALLOWED
            ):
                offenders.append(f"{name}:{node.lineno} {node.value[:60]!r}")
    assert offenders == []


def _engineering_strings(tree: ast.Module) -> set[int]:
    """Ids of string constants that are for us, not the resident.

    Docstrings, anything handed to ``logger.*``, and anything inside a
    ``raise``. Those keep their dashes; only spoken and displayed copy is
    held to A7.
    """
    skip: set[int] = set()

    def mark(node: ast.AST) -> None:
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                skip.add(id(child))

    for node in ast.walk(tree):
        if isinstance(
            node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ):
            if ast.get_docstring(node) is not None:
                skip.add(id(node.body[0].value))  # type: ignore[attr-defined]
        elif isinstance(node, ast.Raise):
            mark(node)
        elif isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "logger"
            ):
                mark(node)
    return skip


#: Non-copy strings that legitimately contain a dash character.
_ALLOWED = frozenset({
    ',.;:!?"\'()[]-—…',  # phrases.py punctuation table: it STRIPS the dash
    " — ",
    "—",
    " – ",
    "–",
})
