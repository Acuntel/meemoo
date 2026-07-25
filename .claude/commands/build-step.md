---
description: Execute one step of the Meemoo build playbook (usage: /build-step 0)
---

You are executing step $ARGUMENTS of the Meemoo build. Meemoo is a round helium
floating companion robot for older adults; the aircraft is dumb, the base
station is smart; hardware doesn't exist yet so everything builds against
stand-ins (webcam, laptop mic, 2D sim). All context lives in this repo.

Do these IN ORDER:

1. Read `docs/CONSTITUTION.md` — every Article is binding. If anything you're
   about to build conflicts with it, STOP and ask Brady.
2. Read `docs/TODO.md` — the checkboxes are the source of truth for what is
   already done. Verify the previous step's gate actually passes (run its tests)
   before starting this one.
3. Read `docs/build-steps/step-$ARGUMENTS.md` and any docs it tells you to read.
4. Build exactly what the step specifies. Follow Brady's global code rules:
   files under 300 lines, type hints everywhere, no bare excepts, structured
   logging, missing credentials never crash startup.
5. Verify: run the step's gate (tests + `make check` once it exists). Fix what
   fails before declaring anything done.
6. Wrap up, always:
   - Check off completed items in `docs/TODO.md` (and note any deviations)
   - `git add -A && git commit` (end message with the Claude co-author line)
     and push to `Acuntel/meemoo`
   - Update `~/.claude/projects/-Users-bradyschwartz/memory/project_meemoo.md`
     with a 2–4 line state delta (what landed, what's next)
   - Tell Brady in plain language: what was built, what the gate proved, and
     that the next command is `/build-step <n+1>`

Rules of the road: never put an API key in the repo; never add biometric
identification; never put a generative model in the safety path; the sim keeps
its honest physics (no loosening constants to make a controller pass). If the
step is impossible as written, say why and propose the smallest amendment —
don't silently improvise around the constitution.
