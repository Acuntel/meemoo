# Helpee

A small, cute, animal-shaped helium blimp that floats at eye level and serves as a
companion + safety check-in device for older adults — at home, in nursing homes, and
in hospitals. It holds conversations, gives reminders, and escalates to family or
staff when someone asks for help or the system detects a possible problem.

**Architecture in one line: the aircraft is dumb, the ground is smart.** The blimp
carries only a camera, mic, speaker, and steering motors (~150 g payload). All
intelligence lives in a wall-powered base station. Since the hardware doesn't exist
yet, the entire brain is being built against stand-ins: laptop webcam/mic as the
blimp's senses, a 2D simulator as the aircraft. When real hardware arrives, only the
I/O drivers get swapped.

## Status

**Phase: research.** Nothing is built yet. Current documents:

| Doc | What it is |
|---|---|
| [docs/MASTER_PROMPT.md](docs/MASTER_PROMPT.md) | The full build spec (modules, data model, demo script, quality bar) |
| docs/RESEARCH.md | Deep research: competitors, physics/size, docking, silence, medical regs *(in progress)* |
| docs/CONSTITUTION.md | What Helpee must be + what we work around *(after research Q&A)* |
| docs/TODO.md | Every piece of software to build and test *(after constitution)* |

## Core principles (short form)

1. The cared-for person is the user; their family / facility staff is the customer.
2. Local-first. Video never leaves the machine except opt-in event clips.
3. Model-agnostic brain — owner plugs in their own AI provider and key.
4. **Own the entire tech stack.** Build it ourselves (voice included) unless a
   third-party option is significantly better or ours provably can't work — and
   even then it lives behind our own adapter so it can be replaced.
5. Graceful degradation everywhere; the safety loop never depends on a third party.
6. Everything observable — every check-in, detection, escalation, and flight is logged.
