# Meemoo

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

## How to build (the /clear workflow)

Each build step is a self-contained prompt; context lives in this repo, so a
fresh session loses nothing. In Claude Code, from this directory:

```
/clear
/build-step 0
```

…then `/build-step 1`, `2`, … in order. Each step reads the constitution and
TODO, builds, verifies its gate, checks off TODO, commits, pushes, and updates
memory. Steps: 0 scaffold · 1 core · 2 perception · 3 voice · 4 brain ·
5 guardian · 6 flight+dock sim · 7 API+web · 8 integration · 9 hardware bench
(see docs/HARDWARE_MANUAL.md) · 10 Isaac 3D investigation · 11 go-live gates.

## Status

**Phase: ready to build.** Research + constitution complete. Current documents:

| Doc | What it is |
|---|---|
| [docs/MASTER_PROMPT.md](docs/MASTER_PROMPT.md) | The full build spec (modules, data model, demo script, quality bar) |
| [docs/RESEARCH.md](docs/RESEARCH.md) | Research synthesis (7 deep-dives in docs/research/) |
| [docs/CONSTITUTION.md](docs/CONSTITUTION.md) | The binding rules — read before building anything |
| [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md) | Feasibility verdict, wings decision, system map, test strategy |
| [docs/TODO.md](docs/TODO.md) | Phase checklist — source of truth for progress |
| [docs/build-steps/](docs/build-steps/) | Self-contained step prompts for /build-step |
| [docs/HARDWARE_MANUAL.md](docs/HARDWARE_MANUAL.md) | Zero-experience hardware guide + bench tests |
| [docs/ORDER_LIST.md](docs/ORDER_LIST.md) | Exact parts, prices, where to buy |

## Core principles (short form)

1. The cared-for person is the user; their family / facility staff is the customer.
2. Local-first. Video never leaves the machine except opt-in event clips.
3. Model-agnostic brain — owner plugs in their own AI provider and key.
4. **Own the entire tech stack.** Build it ourselves (voice included) unless a
   third-party option is significantly better or ours provably can't work — and
   even then it lives behind our own adapter so it can be replaced.
5. Graceful degradation everywhere; the safety loop never depends on a third party.
6. Everything observable — every check-in, detection, escalation, and flight is logged.
