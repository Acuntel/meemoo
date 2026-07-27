# Landmark fixture suites

Two committed suites feed the perception tests:

- `real/` — PRIMARY. MediaPipe landmarks extracted from real GMDCSA-24 and
  CAUCAFall video clips (19 falls, 16 ADLs; day / night / 0-lux IR).
  Licenses + modification notes: real/ATTRIBUTION.md. Asserted by
  tests/perception/test_real_fixtures.py, whose expectations are MEASURED
  behavior with every spec divergence recorded per clip (`spec_gap`) and in
  docs/TODO.md.
- `synthetic/` — fast, fully-controlled CI suite. Procedural stick-figure
  clips (tests/fixtures/generate_synthetic.py) with honest research-05 §A.3
  kinematics; every scenario knob is exact by construction. Asserted by
  tests/perception/test_fall_statemachine.py. Kept because the synthetic
  clips can express things the real datasets cannot (a 90 s long-lie, a
  15 s-down-then-recover, VANISHED_DOWN at the frame edge) and they pin the
  state machine's timers to the threshold file exactly.

Rebuild pipeline for `real/` (raw videos never enter git):

    uv run python -m tests.fixtures.clips.fetch        # ~200 MB, gitignored
    # scratch venv with opencv+mediapipe (see extract_landmarks.py docstring)
    PYTHONPATH=. <scratch>/bin/python -m tests.fixtures.extract_landmarks
    uv run python -m tests.fixtures.bake_real          # annotations -> real/
