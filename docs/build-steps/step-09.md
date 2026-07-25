# Step 09 — Hardware bench (physical; Brady + Claude together)

**Goal:** retire the two derived-not-measured numbers (noise, leak) and make the
funnel-vs-winch capture decision — before any custom hardware.
**Read first:** docs/HARDWARE_MANUAL.md (the beginner-level instructions —
this step IS that manual, executed), docs/ORDER_LIST.md, research/06 §F.

## Prereq
Parts from ORDER_LIST sections A–C ordered and arrived. Balloon-grade ≥99%
helium sourced (NOT a party-store 80/20 tank).

## Run (in this order — each has a full walkthrough in HARDWARE_MANUAL.md)
1. **Noise test** (~1 hr): motor+prop at 20–30% throttle on the bench; SPL
   meter at 1 m; record dBA. Target: ≤45 dB. Software side: log the numbers
   into `docs/bench-results.md`.
2. **Leak test** (runs 2 weeks passively): filled 36" balloon + clay-trimmed to
   ~5 g positive; weigh lift daily on the 0.1 g scale; plot g/day.
   Target: ≤0.6 g/day. This also produces the trim-drift constant for the sim.
3. **Capture test (THE decision, ~20 min once rigged):** neutral-trimmed
   balloon with taped-on nose cone + steel washer, hand-pushed nose-first into
   the foam-board cone at 5/10/15 cm/s and at increasing lateral offsets. Does
   held forward pressure self-center it into the throat, or does it stall on
   the wall? Record the capture radius. → Decides funnel (primary) vs
   magnet-winch (fallback, research/06 §E).
4. **Magnet tests:** electromagnet holds the docked balloon overnight through
   a full HVAC cycle; release on power-cut is clean; measure residual
   remanence pull with the kitchen scale; try the reverse-pulse trick if it
   sticks.
5. **Dock-cam tracking:** webcam + the step-06 tracking code against a balloon
   on a string: ≥20 Hz position output, ~1 cm lateral precision, three
   lighting conditions (day, lamp, dark+IR if the IR kit arrived).
6. **Speaker check:** MAX98357A + 28 mm speaker playing Meemoo's TTS voice at
   1–2 m — intelligible? If an older adult is around (grandparents), ask them.

## Wrap-up
Write every measurement into `docs/bench-results.md`; update the sim constants
(leak rate, capture radius, v_max) from measured reality; check off TODO
Phase 9; commit + push; update memory with the funnel-vs-winch verdict.
