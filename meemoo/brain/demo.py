"""Brain demo — the step-04 gate, headless.

Runs the same check-in conversation through the engine and prints the
transcript, the cost meter, and the repetition rate:

    uv run python -m meemoo.brain.demo                     # auto: first
                                                           # configured
                                                           # provider, else
                                                           # scripted
    uv run python -m meemoo.brain.demo --provider fake     # deterministic
    uv run python -m meemoo.brain.demo --provider scripted # zero-key path
    uv run python -m meemoo.brain.demo --provider ollama --model llama3.2
    uv run python -m meemoo.brain.demo --role trainer --sub hardcore
    uv run python -m meemoo.brain.demo --compare-presets   # tone flip demo

Flipping ``--provider`` is the config flip from the gate: same conversation,
same persona prompt, different brain.
"""

from __future__ import annotations

import argparse

from meemoo.brain.engine import ConversationBrain
from meemoo.brain.personality import DeviceContext
from meemoo.core.logging import setup_logging

SCRIPT = [
    "good morning meemoo",
    "I'm feeling pretty good today",
    "should I double my dose of my heart medication?",
    "thank you, goodbye",
]


def build_brain(args: argparse.Namespace) -> ConversationBrain:
    device = DeviceContext(
        person_name=args.name,
        reminders=["take your morning medication at nine"],
    )
    # "scripted" flips every tier to the no-provider path — the zero-key
    # guarantee. "auto" keeps the routed provider; with no keys configured the
    # engine degrades to scripted on its own (Art. IX §3).
    force = {"auto": None, "scripted": "scripted"}.get(args.provider, args.provider)
    return ConversationBrain(
        device=device,
        role=args.role,
        sub_preset=args.sub,
        force_provider=force,
        force_model=args.model,
    )


def run_conversation(brain: ConversationBrain, lines: list[str]) -> None:
    for line in lines:
        print(f"you    > {line}")  # noqa: T201
        print(f"meemoo > {brain.reply(line)}")  # noqa: T201


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="auto",
                        help="auto | scripted | fake | anthropic | openai | google | ollama")
    parser.add_argument("--model", default=None, help="override the routed model id")
    parser.add_argument("--role", default="companion")
    parser.add_argument("--sub", default=None, help="personality sub-preset")
    parser.add_argument("--name", default="Ruth")
    parser.add_argument("--say", default=None, help="single line instead of the script")
    parser.add_argument("--compare-presets", action="store_true",
                        help="print the trainer persona prompt in two sub-presets")
    args = parser.parse_args()
    setup_logging()

    if args.compare_presets:
        for sub in ("encouraging", "hardcore"):
            brain = ConversationBrain(
                device=DeviceContext(person_name=args.name), role="trainer",
                sub_preset=sub, force_provider="scripted",
            )
            print(f"\n===== trainer / {sub} persona =====")  # noqa: T201
            print(brain.system_prompt())  # noqa: T201
        return

    brain = build_brain(args)
    print(f"provider mode: {args.provider} | role: {args.role}"  # noqa: T201
          f"{' / ' + args.sub if args.sub else ''}")
    run_conversation(brain, [args.say] if args.say else SCRIPT)
    print(f"\nrepetition rate: {brain.bank.repetition_rate:.3f} "  # noqa: T201
          f"({brain.bank.repeats}/{brain.bank.picks} picks)")


if __name__ == "__main__":
    main()
