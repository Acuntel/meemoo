# Helpee — Research Synthesis (2026-07-25)

Seven deep-dive reports live in [docs/research/](research/): [01 competitors](research/01-competitors.md) ·
[02 voice stack](research/02-voice-stack.md) · [03 regulatory](research/03-regulatory.md) ·
[04 hardware](research/04-hardware.md) · [05 fall detection](research/05-fall-detection.md) ·
[06 docking](research/06-docking.md) · [07 SAR academic](research/07-sar-academic.md).
This document is the synthesis: the verdict, what the research changes in the spec,
and the open decisions. It feeds docs/CONSTITUTION.md (written after Brady's answers).

---

## The verdict in one paragraph

The idea survives contact with the evidence — and comes out *more* specific, not less
ambitious. Nobody has ever shipped an indoor companion blimp; the giants who tried
flying/rolling home robots (Ring, Samsung, Amazon) all died on rotor noise, downwash,
or floor navigation — exactly the physics helium sidesteps. Academia just named the
category ("soft floating robots," Keio/MIT, DIS 2026) and proved people spontaneously
hug them, and Matarić's own lab published the embodiment result that justifies the
whole product. The physics is friendly: near-silence is free with buoyancy, endurance
is a non-issue, bump recovery is mostly passive. The two genuinely unsolved problems
are **autonomous docking** (never demonstrated for a micro-blimp — our biggest risk and
our moat) and **helium trim drift** (solvable with a $3 load cell + dock-side auto
top-off). The two hard business truths: the proven buyer is a **state aging agency**,
not a consumer, and the BYO-API-key differentiator is a developer feature in a market
with zero developers. The safety architecture ("no auto-911," local-first, no
biometric templates) turns out to be not just nice-to-have but the exact set of
choices that keeps Helpee out of FDA premarket regulation, Illinois BIPA class
actions, and wiretap liability.

## What the research VALIDATES (keep, and say louder)

1. **Dumb aircraft / smart base station.** Independently converged on by Georgia Tech
   (GT-MAB), Edinburgh, Keio, and the blimp-swarm literature. Payload-constrained
   researchers all offload compute to the ground. Saying this in the pitch is a
   credibility marker.
2. **The blimp form factor for this population.** Peer-reviewed: 92% of participants
   spontaneously touched/hugged a soft floating robot (Cuddle-Fish, N=24); GT-MAB
   demonstrated face-following + gestures from one onboard camera; blimps framed in
   HRI literature as the safe class where quadcopters fail.
3. **Embodiment.** Kian et al. 2025 (Matarić lab): same LLM, engagement and disclosure
   *rose* over two weeks with a robot and *fell* with a chatbot. The answer to "why
   not a smart speaker."
4. **Near-silent flight.** Physics gift: 50–150× less thrust than a quadcopter →
   estimated 35–45 dB @ 1 m. UAV-noise research confirms quiet homes are the *hardest*
   acoustic context, making buoyant lift the strongest technical argument.
5. **No auto-911 in v1.** The single highest-leverage regulatory decision already
   made. Keeps Helpee outside FDA's own worked example of a regulated device (ILQ).
6. **Local-first privacy.** Maps exactly onto what elders accept (50-study review):
   blurred/anonymized processing, decisional control, no raw video egress.
7. **Own-the-stack (the constitution principle).** The voice research says the
   constitution *wins*: best self-hosted STT beats Whisper-large (Moonshine, MIT),
   best MIT-licensed TTS beat ElevenLabs in a blind test (Chatterbox Turbo 65% vs
   25%). The only justified exception: the frontier LLM brain (hosted primary, local
   8B as a real fallback — same voice either way, so the user can't tell).

## What the research CHANGES in the spec (concrete deltas)

| # | Spec said | Research says | Delta |
|---|---|---|---|
| 1 | ~150 g payload | Real BOM ≈ 49 g + margin = **65 g** → **~120 L envelope** (whale ~0.95 × 0.48 m) | Retarget sim + MQTT spec constants |
| 2 | "Two average balloons" size wish | 28 L lifts 17 g — physically out. 120 L is only 1.6× the width of 28 L; bigger is *calmer* in drafts | Accept ~120 L (or go 250–300 L for the plush skin) |
| 3 | Funnel dock, blimp "lands" | A funnel doesn't center a neutrally buoyant vehicle. **Nose-first horizontal cone + held thrust + dock-side electromagnet + concentric ring contacts**; ~4 g / $3.50 aircraft-side | Dock redesign; add `DockController` beside `FlightController` |
| 4 | (unstated buoyancy) | **Trim negative** (2–4 g heavy): power loss = gentle descent, not ceiling-parking | Design invariant |
| 5 | Fall heuristic = horizontal AND still 15 s | **Persistence-primary, descent corroborating** (never AND). Add LONG_LIE + VANISHED_DOWN paths, floor-line + furniture-zone calibration with a learning phase, CANDIDATE_SOFT for deliberate floor-sitters | Rewrite perception spec §heuristic |
| 6 | Blimp camera detects falls | **Base station camera (mounted high) is the detector; the blimp is the verifier + conversation.** Published three-stage architecture scores 96.3% at stage-3 confirmation | Perception runs on base cam; blimp cam = verification bursts |
| 7 | faster-whisper + Piper | **Moonshine v2 Streaming** (beats whisper-large at 1/6 size, no silence-hallucination — critical for elderly pauses) + **Pocket TTS/Chatterbox** (Piper = offline floor). All self-hosted, all "ours" | Swap model picks behind same interfaces |
| 8 | Wake word "if practical" | microWakeWord on ESP32-S3 is proven. But **"Helpee" is a dangerous wake word** (collides with "help" — the distress word). Ship "Hey Helpee" + a separate always-on low-threshold "help" distress model with opposite tuning | Two models, never one |
| 9 | BYO API key as THE differentiator | It's a developer feature in a market with zero developers (every successful competitor bundles inference). Keep model-agnosticism as internal architecture/vendor hedge | Reposition; Setup Studio de-emphasizes keys |
| 10 | "greets Ruth by name" implies identity | **No face recognition, no speaker ID in v1** (Illinois BIPA class-action risk; voiceprints named in the statute). Identity via schedule/context/asking | Architectural prohibition, written down |
| 11 | Escalation may use LLM reasoning tier | **No generative model in the safety path** (also Matarić's own lab's bar). LLM never ranks clinical severity; escalation = deterministic state machine routing "non-clinical events" | Guardian stays template-driven; brain advises only on non-safety |
| 12 | Dashboard = family view | Add the **research-credibility layer**: engagement trajectory (user-initiated share over time), adherence with prompts-required, false-alarm budget as a headline number, UCLA-LS check-in cadence, human-contact tracking (anti-substitution metric), data export + synthetic-data demo mode | New dashboard panels; cheap, hugely differentiating |
| 13 | (unstated) | **AI-disclosure compliance is already legally required** (NY live 11/2025, CA live 1/2026): spoken AI disclosure, 3-hour reminders, 988 crisis protocol with logged referrals | Build into voice module v1 |
| 14 | (unstated) | **Spatial policy** from proxemics data: conversational mode ≈1.5–1.8 m at/below eye level with vocal announcement; ambient mode above head, constant radius; never spin overhead | Flight/sim behavior parameters |
| 15 | (unstated) | **Anti-surreptitious design** defeats all-party-consent risk: audible self-announcement entering rooms, visible recording indicator, hardware mic mute, no raw-audio retention by default | Product + voice design |

## Top risks, merged and ranked

1. **Autonomous docking is unsolved** (nobody has done it) — retire with the $40
   balloon-and-cone bench test *before* any custom hardware; build the docking loop
   in the sim now. Fallback exists (Auckland magnet-winch, published).
2. **Illinois BIPA** — the only risk with a private right of action and statutory
   damages. Fix is architectural and verifiable: no biometric templates, ever.
3. **Helium trim drift** = recurring maintenance on the least-suitable user. Fix:
   dock load cell + cartridge auto top-off (also the subscription mechanism).
   Gas cost itself is a rounding error (~$10–25/unit/yr even post-Qatar-shock).
4. **AI-companion-law compliance** — in scope today; a floating companion talking to
   an elder is the most sympathetic enforcement target imaginable. Over-comply.
5. **Marketing claims** — the cheapest way to accidentally become an FDA device and
   lose a lawsuit simultaneously. Forbidden-terms list goes into CI lint.
6. **Abandonment** (the quiet killer): one-third of assistive tech abandoned in a
   year; drivers are lack of enjoyment + lack of usefulness. The engagement
   trajectory + abandonment early-warning composite is the countermeasure.
7. **Helium supply optics** — Qatar strike took ~⅓ of world supply offline 3/2026;
   consumer party tanks are now 80/20 He/air (20% lift loss — unusable). Contract
   ≥99% balloon-grade early; have the answer rehearsed for investors.

## The business picture (from 01)

- **Proven buyer:** state aging agencies (NYSOFA × ElliQ = $2.1M/3yr ≈ $65/mo/senior;
  Korea × Hyodol = 12,000 units). 6–18 month RFP sales.
- **Proven consumer band:** $30–50/mo + $200–300 upfront (PERS/ElliQ anchors);
  >$60/mo needs a monitored call center.
- **Sequencing (regulatory geography):** private homes → assisted living → skilled
  nursing → hospitals. Hospitals last (NFPA 99 helium storage, IEC 60601, infection
  control — all solvable, all paperwork-heavy).
- **The actual product** = floating form factor + safety/escalation layer +
  procurement channel, combined. No one has combined them. The blimp alone is not
  the moat; Keio/MIT publish but don't commercialize, and BOOBOO (CES 2026) flies
  but has no safety layer.

## Hardware next steps (when Brady wants to spend ~$150)

1. 36" mylar balloon + XIAO ESP32S3 Sense + 4 coreless motors + $30 SPL meter →
   measure real noise + leak rate in a week.
2. Cardboard cone + $5 electromagnet + ballasted balloon → the 20-minute test that
   decides funnel-vs-winch (the single biggest open hardware question).
3. Both experiments before any custom envelope or PCB.

## Open decisions for Brady (full question list delivered in chat 2026-07-25)

Size class (120 L film vs 300 L plush) · first-customer thesis (agency vs consumer)
· BYO-key repositioning · name/wake-word · Matarić-demo timeline + scope · pilot
study doc · base-station hardware target · transcripts default · budget/timing for
bench experiments · sim floor plan source.
