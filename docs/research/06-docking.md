# Research 06 — Autonomous Docking Deep-Dive (July 2026)

> Produced 2026-07-25 by the docking research agent. Part of the Helpee
> pre-build research phase. See docs/RESEARCH.md for the synthesis.

**Headline:** this problem has been solved before, twice, for almost exactly this vehicle. The published prior art converges on the architecture already picked (dumb aircraft, smart ground station) and it tells you the one thing that is genuinely counterintuitive: **a funnel does not passively centre a neutrally buoyant vehicle, so v1 must supply an active centring force.** Everything else — guidance precision, retention, charging — is comfortably within reach with off-the-shelf parts, at about **4 grams of aircraft-side penalty and ~$60 of dock**.

Two caveats on sourcing up front: the session's web-search budget was exhausted partway through, so a few numbers below are labelled *[estimate — verify]* rather than cited. And IEEE/ResearchGate/Academia paywalls blocked full text on the single most relevant paper (Auckland magnet-winch), so only its abstract and figure captions are in hand.

---

## Prior art that matters (read these first)

**1. Probine, Gorjup & Liarokapis — "A Shared Control Teleoperation Framework for Robotic Airships: Combining Intuitive Interfaces and an Autonomous Landing System"** (IEEE, University of Auckland "New Dexterity" group). This project's closest ancestor: a *miniature indoor* robotic airship with an autonomous landing-and-charging system. The landing system uses **ArUco markers plus an onboard camera** for state estimation. The docking station uses a **magnet-based winch mechanism that catches the airship and pulls it into position for charging**, while the airship controls its yaw to align with the charging pad. All station structure is 3D-printed PLA. <https://ieeexplore.ieee.org/document/9659088/> · <https://www.semanticscholar.org/paper/8a031bc9981339c1654328c92880aad4db153b68> · demo video <https://www.youtube.com/watch?v=BC483DQN5Vg>

The winch is the tell. A competent robotics group solving this exact problem chose an *actively actuated pull-in* over a passive pad or funnel. Not an accident — section B explains why.

**2. Takaya et al. — "PID landing orbit motion controller for an indoor blimp robot"** (Artificial Life and Robotics, 2006) and **Kawamura/Yamamoto/Takaya — "Learning landing control of an indoor blimp robot for self-energy recharging"** (ALR, 2007/08). Explicitly framed around this bottleneck: indoor blimp payload is too small to stack batteries, so autonomous docking to a charging station is the enabler for long-duration operation. <https://link.springer.com/article/10.1007/s10015-006-0385-9> · <https://link.springer.com/article/10.1007/s10015-007-0451-y>

**3. Alkurdi & Fisher — "Visual Control of an Autonomous Indoor Robotic Blimp"** (University of Edinburgh). This architecture, built and flown: *"A network camera fixed to the ceiling provides the images for the image processing algorithms. The processing is done on a laptop, and the motor commands are sent to the blimp via wireless LAN interface."* Their stated reason: *"Payload, when speaking about blimps, is a function of envelope size, and with small blimps limited payload means limited amount of sensors."* Waypoint tracking with a fuzzy controller, robust to HVAC draft disturbances from doors, stairs and elevators. <https://homepages.inf.ed.ac.uk/rbf/PAPERS/VisualControlBlimp.pdf>

Two warnings from that paper to design around. First, they cite van der Zwaan et al. (2000), who did onboard-vision station-keeping *and docking* on a small blimp and found it **"had difficulties with lateral movements of the blimp due to air currents, as this blimp does not have lateral degrees of freedom to control"** — the workaround was yaw rotation, which introduced oscillation. Give the blimp either genuine lateral thrust or a docking approach that never needs it. Second, their envelope leaked helium enough to change buoyancy measurably between test runs.

**4. Georgia Tech GT-MAB** — the reference miniature indoor blimp platform. Payload budget **under 80 g**, so **most computation is performed offboard on a base-station computer**; ~2 hour flight endurance because hovering is the default state of a neutrally buoyant vehicle. <https://www.gtsr.gatech.edu/2017/06/08/georgia-tech-miniature-autonomous-blimp-gt-mab-is-featured-in-ieee-spectrum/> · <https://arc.aiaa.org/doi/10.2514/6.2022-1834>

**5. CERN indoor blimp** (open access) — the most useful hard-numbers paper. 0.70 m³ envelope, 1.5 × 0.6 × 0.6 m, 450 g total mass, 200 g payload, 8 coreless brushed motors with 4 cm fans, and critically: **thrust saturation of ±0.1 N (≈10 gram-force) per motor**. <https://pmc.ncbi.nlm.nih.gov/articles/PMC10611505/>

That 10 gf/motor figure constrains the entire dock design.

---

## A. Guidance options

Precision required at the dock throat is set by the capture aperture, not by ambition. With a 15–20 cm funnel mouth you need roughly **±7 cm lateral** at contact — which almost everything below clears. So choose on *weight and architecture fit*, not precision.

| Option | Precision | Aircraft weight | Cost | Demonstrated where |
|---|---|---|---|---|
| **Dock/ceiling camera tracks blimp, base station closes loop** | ~1 cm lateral *[estimate: 1080p over a 4 m field ≈ 2.1 mm/px; centroid to ~5 px]*; range is the weak axis | **~0.3 g** (passive IR-reflective or high-contrast dots) | $15–30 (USB/Pi cam) | Alkurdi & Fisher ceiling cam + laptop + WLAN; Kawai et al. ceiling cam tracking two painted dots on the envelope; the entire mocap-guided blimp literature is the lab-grade version |
| **Onboard camera + ArUco/AprilTag on dock, decoded on base station** | few mm–1 cm lateral at 1–2 m with a ~10 cm tag *[estimate — verify]*; out-of-plane rotation and range are the noisy axes | **0 g incremental** — reuses the camera the product already carries | $0 (printed tag) | Probine et al. on this exact vehicle class; PX4 supports it via `LANDING_TARGET`; standard on ground robots (<https://pmc.ncbi.nlm.nih.gov/articles/PMC12196723/>) |
| IR beacon homing (IR-LOCK + MarkOne) | **~10 cm**, cited by both PX4 and ArduPilot; earlier work reported 5–30 cm | ~10–25 g (Pixy-class smart camera + I2C host) + a downward rangefinder | ~$150+ | PX4 <https://docs.px4.io/main/en/advanced_features/precland> · ArduPilot <https://ardupilot.org/copter/docs/precision-landing-irlock.html> · <https://irlock.com/collections/precision-landing> |
| UWB | ~10–30 cm typical | ~3–6 g tag | ~$20/tag + 3–4 anchors | Mature for room-scale, not for centimetre docking |
| Ultrasonic beacons (Marvelmind-class) | ~2 cm claimed | ~10–20 g aircraft beacon | ~$300+/set | Too heavy; audible-adjacent hardware is a poor fit for a companion device |
| BLE AoA | ~0.5–1 m | ~2 g | ~$30 | Nowhere near sufficient — rule out |

**Verdict: run the top two together, both processed on the base station.** They are complementary. The dock camera gives absolute blimp pose from ~4 m out and keeps working when the blimp faces away from the dock; the onboard-camera ArUco read gives high-precision *relative* pose in the last ~50 cm when the tag fills the frame. IR-LOCK, UWB, ultrasonic and BLE all put mass and intelligence on the aircraft, which is backwards for this architecture. Treat IR-LOCK's ~10 cm as the benchmark the vision chain must beat, not a component to buy.

**One non-obvious geometry decision.** Mount the dock camera *looking outward along the approach corridor*, not down from the ceiling. A single camera measures lateral offset well and range poorly — and range is precisely the axis the funnel forgives. Pointing the camera down the approach axis aligns its best axis with the tightest tolerance. It also removes the ceiling-mount install problem from a consumer product.

For reference on what money buys: **DJI Dock 2** combines RTK (±3 cm) with visual positioning-marker recognition on the pad — *and still adds a mechanical "slide-ramp centering design" to raise landing success rates.* <https://www.heliguy.com/blogs/knowledge-base/how-is-the-precision-landing-of-dji-dock-2-achieved/> · <https://enterprise.dji.com/dock-2/faq> Even with centimetre RTK, the commercial state of the art does not trust guidance alone.

---

## B. The last 30 centimetres — capture and retention

### The thing to get right

**A funnel centres a quadcopter because gravity pushes it down the cone walls. A neutrally buoyant blimp has no such force.** Touch a cone wall off-centre with zero net weight and the vehicle simply stalls there, or slides unpredictably along the wall. Passive funnel self-centring — Roomba ramps, boat cone moorings, CubeSat docking cones — is *gravity-* or *momentum-*driven, and a blimp has neither: net weight ~0 gf by design, and momentum must stay tiny to avoid bouncing off.

This is why the Auckland group built a winch instead of a funnel. There are only three ways around it:

1. **Substitute forward thrust for gravity.** Approach nose-first into a horizontal cone and *hold forward thrust through insertion*. The cone wall's normal force resolves forward thrust into a centring component exactly as gravity would. Works, costs nothing, and is why nose-first horizontal docking beats landing on a pad.
2. **Actively pull the vehicle in** (the Auckland magnet-winch): a dock-side actuator reaches out and takes over. Decouples capture from the blimp's feeble thrust entirely.
3. **Let a magnet's force gradient do the last centimetre.** Magnetic attraction rises steeply as the gap closes, so once within ~1–2 cm the vehicle snaps in. The finisher for either of the above, not a substitute.

### The force budget

Everything scales off two numbers: **~10 gf of thrust per coreless motor** (CERN paper, ±0.1 N) and a **net buoyancy error of a few gf** that drifts with temperature and helium loss. So retention must beat single-digit gram-forces — while release must be achievable by a vehicle that can push with maybe 5–20 gf total.

That asymmetry kills one option outright. A K&J **D42 disc (6.35 × 3.17 mm, N42) weighs 0.75 g and pulls 1.04 kg against a steel plate** (<https://www.kjmagnetics.com/proddetail.asp?prod=D42>). A permanent-magnet pair is therefore ~100× stronger than the blimp's entire thrust authority: **once stuck, it can never leave.** Retention must be *switchable from the dock side.* The single hardest constraint in the whole system.

*(Sourcing note: K&J lists the smaller D21 at 0.94 g, inconsistent with its geometry — NdFeB at ~7.5 g/cm³ computes to ~0.1 g. Their page looks wrong; the D42 figure checks out against density.)*

| Retention option | Holds? | Aircraft weight | Release mechanism | Verdict |
|---|---|---|---|---|
| **Dock-side electromagnet + aircraft-side steel disc** | Yes, hugely over-margin | **~0.8 g** (a steel washer) | Cut current, plus a brief reverse pulse to kill core remanence | **Primary.** All 22.7 g of magnet sits on the wall-powered dock. Adafruit 5V P20/15: 2.5 kg holding, 0.22 A at 5 V = 1.1 W. <https://www.adafruit.com/product/3872> |
| Permanent magnet on a servo-retracted dock mount | Yes | ~0.8 g | Servo mechanically withdraws the magnet | **Documented variant.** Zero standby power, survives a power cut, but adds the system's most likely wear item (~7,000 actuations over 5 years at 4 docks/day) |
| Permanent magnet on both sides | Yes | ~0.8 g | **None achievable** — 1.04 kg vs ~15 gf of thrust | **Rule out** |
| Dock-side mechanical latch / gripper | Yes | 0 g | Actuator opens | Viable but more parts and more ways to jam than a magnet |
| Continuous downward thrust hold | No | 0 g | n/a | **Rule out.** Burns battery while charging; single-digit-gf thrust cannot fight a draft |
| Negative-buoyancy trim via air ballast pump | Partially | **~30–60 g** | Vent | **Rule out on mass.** Gaining 3 gf means storing ~2.4 L of air; tank, pump and valve blow a third of the payload budget to solve a problem a 0.8 g washer solves |

**Why the magnet is not optional.** Buoyancy drifts in *both* directions. If the envelope is 3 gf light on a warm afternoon, gravity will not hold it in any cradle — it floats out. A magnet clamps in both directions and is indifferent to the sign of the error.

**Release.** With a dock-side electromagnet, departure is nearly free: drop current, apply a short reverse pulse (soft-iron core remanence can retain a few gf — exactly the relevant force scale, so this detail is load-bearing), then reverse thrust to back out along the approach axis. Power failure while docked releases the blimp, which drifts slowly and harmlessly — a benign failure mode, arguably the right one for a device in someone's home.

**Impact energy is a non-problem.** Effective mass is vehicle plus added mass ≈ displaced air, roughly 130 g + ~100 g ≈ 230 g. At 10 cm/s, kinetic energy ~1 mJ. You can bump the funnel all day. The corollary: added mass roughly *doubles* effective inertia, so the blimp coasts; a controller tuned without modelling this will sail straight past the throat.

---

## C. Power transfer — verdict

**Contacts win decisively on weight; specifically, concentric rings integrated into the cone.**

| | Qi / inductive | Concentric ring contacts |
|---|---|---|
| Aircraft-side mass | **8 g** (Adafruit 1901, BQ51013B, 5 V @ 500 mA, 40 × 29 mm coil) <https://www.adafruit.com/product/1901> | **~2 g** (two brass rings on a printed nose cone) |
| Alignment tolerance | Tight — a few mm *[estimate — verify]* | Loose; yaw-independent by symmetry |
| Yaw sensitivity | Requires coplanar coils | **None** |
| Efficiency | ~70–80%, heat in the aircraft | ~99% |
| Long-term failure mode | Coil detune, thermal | Oxidation, dust |

8 grams is 5–8% of the entire payload on a component that also demands *tighter* alignment than the funnel provides. Reject Qi for v1.

**The elegant part: a cone is already a concentric contact surface.** One conductive band around the inside of the cone, the throat face as the second conductor. The blimp's nose probe carries a tip contact and a collar contact. Insertion depth makes the connection and **yaw is irrelevant by rotational symmetry** — which matters enormously, because a blimp cannot promise yaw within a few degrees (van der Zwaan's oscillation problem). Same principle as orientation-independent charging rings on robot vacuums.

Make the **dock** side the spring-loaded pin or leaf contact and the **aircraft** side a plain gold-plated pad. Spring contacts wipe on insertion, which self-cleans oxidation — and the spring, the wear item, lives where mass is free and service is possible. Duty: 4 docks/day × 365 × 5 years ≈ **7,300 cycles**, versus ~1,000,000-cycle ratings typical of quality spring pins *[estimate — confirm against a Mill-Max or Preci-Dip datasheet]*. Gold plating both sides.

**Battery and unattended-charging safety.** A 1S 500–1000 mAh LiPo is 1.85–3.7 Wh. At ~2.5 W a 500 mAh cell refills in well under an hour — comfortably fast for 10–20 min flights and several docks a day.

On fire risk in an older adult's home, treat this as product-existential. The strongest mitigation is that **the pack is tiny** — 1.85 Wh ≈ 1/40 of a phone battery. Then layer:

- **Charge management on the dock**, where grams are free: real CC/CV control with current sensing, not a bare TP4056.
- **Aircraft-side minimum**: a 1S protection IC and a thermistor, ~0.5 g total.
- **Conservative rate** (0.5C) and a **hard independent hardware timer** that cuts dock power regardless of what the firmware believes.
- **Pack temperature over the radio**, dock cuts power on over-temp; never charge below ~5 °C (lithium plating).

**LiFePO4 is worth the mass if the budget closes.** Roughly 40–50% more pack mass for the same energy — on a 10–20 g pack that is **+5–10 g** — for a chemistry without the same severity of thermal runaway. At 3.2 V nominal a 1S cell may sit below ESP32 headroom and need a boost converter. Recommendation: spend the 5–10 g. "The flying thing in grandma's house caught fire" is not a bug you get to fix in v2.

---

## D. Proposed v1 dock design

**Nose-first horizontal docking into a wall- or base-station-mounted cone, guided by a dock camera looking down the approach corridor, captured by held forward thrust, retained by a dock-side electromagnet, charged through concentric ring contacts in the cone.**

Mounting at table or chest height rather than the floor is a real product win: no floor obstacle to trip over, and the dock lives where the base station already is.

**The chain, link by link:**

| Phase | Mechanism | Justification |
|---|---|---|
| **Transit** (4 m → 1.5 m) | Dock camera tracks blimp markers; base station radios steering | Alkurdi & Fisher: ceiling cam → laptop → WLAN commands, flown successfully |
| **Align** (1.5 m standoff) | Yaw to dock axis, null lateral error, hold; onboard camera acquires the dock ArUco tag | Probine et al. used exactly ArUco + onboard camera on an indoor airship; yaw-align-then-approach dodges van der Zwaan's lateral-authority trap |
| **Final approach** (1.5 m → contact) | Creep ≤10 cm/s. Abort if lateral error exceeds the funnel's capture radius | Impact energy ~1 mJ makes slow approach free; PX4 gates its phases on a 0.2 m horizontal-accuracy threshold |
| **Capture** (last 10 cm) | Cone converts *held forward thrust* into centring; magnet snaps the final 1–2 cm | The core insight from section B — thrust substitutes for the gravity a blimp doesn't have |
| **Retain** | Dock electromagnet on; aircraft cuts all thrust once capture confirms | 2.5 kg against a few gf of drift; 22.7 g of magnet costs the aircraft nothing |
| **Charge** | Concentric rings; CC/CV and safety cutoffs on the dock | Yaw-independent, ~2 g, ~99% efficient |
| **Release** | Cut current + reverse demagnetising pulse; reverse thrust out along the axis | Remanence is a few gf — same scale as control authority, so the pulse matters |

### Aircraft side — the whole docking capability

| Part | Grams | $ |
|---|---|---|
| Printed nose cone with two brass ring contacts | 2.0 | 1 |
| Steel capture disc (can double as a contact ring) | 0.8 | 0.20 |
| IR-reflective / high-contrast tracking dots (3) | 0.3 | 0.50 |
| 1S protection IC + thermistor | 0.5 | 1.50 |
| Wiring | 0.7 | 0.30 |
| **Total** | **~4.3 g** | **~$3.50** |

**Four grams and under four dollars.** The number to hold in mind when anyone proposes putting a smart camera, a UWB tag or a Qi coil on the aircraft.

### Dock side

| Part | $ |
|---|---|
| Printed cone/funnel, PETG (~150 g filament) | 3 |
| 5 V electromagnet P20/15 (22.7 g, 1.1 W) | 5 |
| Concentric contact rings + spring contacts, gold-plated | 5 |
| 1S charge module with current sense | 3 |
| Hall or reed switch (capture confirmation) | 1 |
| Dock camera (Pi cam or USB) | 15–30 |
| IR illuminator ring (low-light tracking) | 5 |
| MOSFET driver, connectors, misc | 5 |
| 5 V 3 A PSU | 8 |
| **Total** | **~$50–65** |

**Confirm capture with two independent signals** — charge-contact continuity *and* the hall/reed switch — never with vision alone. Vision cannot distinguish "docked" from "resting against the outside of the cone", and that mistake ends with a blimp that cut its thrust while not actually captured.

**Envelope sizing, for consistency.** Helium nets ~1.06 gf/L; a ~160 L envelope in mylar (~20 g/m² over ~1.4 m²) nets ~130 g for gondola, battery and payload — a ~0.66 m sphere or ~1.0 × 0.5 m ellipsoid. Between GT-MAB (<80 g payload) and the CERN blimp (200 g).

**The problem adjacent to docking that will bite.** Buoyancy is never stable. A 3 °C room-temperature swing changes lift by ~2 gf on a 160 L taut envelope, and helium diffusion costs perhaps 1–2% of volume per day — call it 1.5–3 gf of lift per day *[estimate; Alkurdi & Fisher independently report buoyancy changing between test runs]*. So the vehicle drifts from neutral to several grams heavy within days and needs periodic top-up. The dock is the natural place to instrument this: steady-state vertical-thruster duty cycle during hover *is* a net-buoyancy measurement. Log it, trend it, and the product can say "Helpee needs a helium top-up this week" before it starts sinking. Build the telemetry in v1 even though the refill stays manual.

---

## E. Fallback design

**Riskiest link: capture.** Specifically, whether held forward thrust reliably centres the nose down the cone at single-digit gram-forces against household drafts. If not — if the blimp stalls against the cone wall, or drafts push it off-axis faster than 10 gf can correct — the fallback is published prior art:

**Fallback: the Auckland dock-side magnet-winch.** Replace passive cone geometry with an actuated dock-side arm or tethered magnet that extends toward the blimp, magnetically grabs the nose disc at 10–20 cm, and *pulls it in.* Eliminates the aircraft's thrust from the capture problem entirely — the dock does the work, with unlimited power and mass. Cost: one small geared motor or servo plus a spool, maybe +$15 and one moving part.

Strictly more capable than the primary; ranked second only because it adds a wear item that must survive ~7,000 cycles unattended. If the section-F experiment shows thrust-through-cone is marginal, promote the winch without hesitation — the group that built this exact vehicle chose it first.

**Secondary fallbacks:** if the electromagnet's remanence proves un-releasable or 1.1 W standby is unwelcome, swap to the servo-retracted permanent magnet (also gains power-cut retention). If the dock camera cannot hold ~1 cm through varied home lighting, add the IR illuminator ring first, then fall back to onboard-camera ArUco as primary with the dock camera demoted to transit-only.

---

## F. First prototype experiment — retire capture risk for ~$40

Do this **before any custom envelope, flight code or PCB exists.** No electronics on the aircraft at all.

**Build:** a 90 cm mylar party balloon, ballasted to neutral with modelling clay, with a taped-on printed nose cone carrying a steel disc. A cardboard or printed cone with the electromagnet at the throat, on the bench.

**Measure, by hand-flying the balloon:**
1. **Capture envelope** — the maximum lateral offset the cone absorbs at 5, 10 and 15 cm/s. This one number sizes the whole guidance requirement. If ±7 cm or better, everything in section A clears with margin.
2. **Does held forward thrust actually centre it?** Push the balloon in gently off-axis: does it slide to the throat or stall on the wall? **This is the primary/fallback decision, and it is a 20-minute test.**
3. **Overnight hold** through a full HVAC cycle. Does it stay? Does buoyancy drift pull it out?
4. **Clean release** — does cutting current let go, and is a reverse pulse needed? Measure residual hold in gram-force with a kitchen scale.

**Phase 2 (same rig, +1 day):** add the contact rings, do a few hundred manual insertions while logging charge current. Watch for contact-resistance creep and intermittency — this is where you learn whether the wiping action really self-cleans.

**In parallel, software side:** develop the dock-camera tracking loop against a **balloon on a string** moved by hand. Target: position output at ≥20 Hz with ~1 cm lateral precision under three lighting conditions. No aircraft required; de-risks guidance independently.

Total cost of retiring both major risks: roughly a weekend and under $100.

---

## G. Software interface requirements

Model docking as an **explicit state machine**, and treat the **dock as its own device** with its own interface. In the real system the dock is wired to the base station while the aircraft is on radio; conflating `FlightController` with dock actuation will hurt later. Add a sibling `DockController`.

### States

`FLYING` → `DOCK_REQUESTED` → `TRANSIT` (to a 1.5 m standoff on the dock axis) → `ALIGN` (yaw to axis, null lateral error, hold) → `FINAL_APPROACH` (creep, abort on excess lateral error) → `CAPTURE_PENDING` → `CAPTURED` (retention engaged, thrust zeroed) → `CHARGING` → `CHARGE_COMPLETE` → `RELEASE` → `DEPARTED` → `FLYING`

Plus `ABORT` from any approach state back to standoff with a retry counter, and `DOCK_FAILED` after N attempts. Mirrors PX4's three-phase structure (Horizontal Approach → Descent Over Target → Final Approach, gated on `PLD_HACC_RAD` = 0.2 m, with `PLD_BTOUT` target-loss timeout and `PLD_MAX_SRCH` retry cap) — worth copying deliberately. <https://docs.px4.io/main/en/advanced_features/precland>

### Telemetry the interface needs

**Relative pose — from the dock/base station, not the aircraft:** `lateralError_mm`, `verticalError_mm`, `rangeToThroat_mm`, `yawError_deg`, `trackingValid`, `trackingAge_ms`. That last field is the `PLD_BTOUT` analogue and prevents a stale-estimate crash into the wall.

**Capture — two independent channels, never one:** `retentionEngaged`, `contactContinuity`, `captureSwitch`. Require agreement before entering `CAPTURED`.

**Charging:** `chargeCurrent_mA`, `packVoltage_mV`, `packTemp_C`, `chargeState: none|bulk|topping|complete|fault`, `chargeFaultReason`.

**LTA-specific, and the one nobody thinks to add:** `netBuoyancy_gf`, derived from steady-state vertical-thruster duty during hover, plus a `hoverThrustDuty` history. Tells the approach controller whether the blimp will float up or sink during final approach *and* drives the helium top-up prediction. Cheap to compute, disproportionately valuable.

### Commands

`requestDock()`, `abortDock()`, `requestUndock()`, `holdStandoff()` on the flight controller; `setRetention(bool)`, `setChargeEnabled(bool)` on the **dock** controller.

### What the simulator must model

Get these five right and the real controller slots in with retuning rather than a rewrite:

1. **Added mass ≈ displaced air mass** — roughly doubles effective inertia. Omit this and every approach controller tuned in sim will overshoot the throat.
2. **Net buoyancy as a tunable, slowly drifting parameter in gram-force.** Docking must be proven across ±5 gf, both signs. Randomise per episode.
3. **Thrust saturation at realistic single-digit gram-force** per thruster (±0.1 N measured, CERN platform). Generous sim thrust limits are the fastest way to build a controller that cannot exist.
4. **A funnel capture model:** capture succeeds iff |lateral error| < R_capture at throat contact **and** approach speed < v_max; otherwise bounce off and abort. Parameterise from the section-F bench measurements.
5. **HVAC draft disturbance** as the dominant indoor error source — a low-frequency wandering force of a few gram-force, the same magnitude as control authority. That collision of scales *is* the control problem.

---

## Sources

- [Probine, Gorjup & Liarokapis — Shared Control Teleoperation Framework for Robotic Airships (IEEE)](https://ieeexplore.ieee.org/document/9659088/) · [Semantic Scholar](https://www.semanticscholar.org/paper/A-Shared-Control-Teleoperation-Framework-for-and-an-Probine-Gorjup/8a031bc9981339c1654328c92880aad4db153b68) · [demo video](https://www.youtube.com/watch?v=BC483DQN5Vg)
- [Takaya et al. — PID landing orbit motion controller for an indoor blimp robot](https://link.springer.com/article/10.1007/s10015-006-0385-9)
- [Kawamura/Yamamoto/Takaya — Learning landing control of an indoor blimp robot for self-energy recharging](https://link.springer.com/article/10.1007/s10015-007-0451-y)
- [Alkurdi & Fisher — Visual Control of an Autonomous Indoor Robotic Blimp (PDF)](https://homepages.inf.ed.ac.uk/rbf/PAPERS/VisualControlBlimp.pdf)
- [Georgia Tech Miniature Autonomous Blimp (GT-MAB)](https://www.gtsr.gatech.edu/2017/06/08/georgia-tech-miniature-autonomous-blimp-gt-mab-is-featured-in-ieee-spectrum/) · [Miniature Autonomous Blimps for Indoor Applications (AIAA)](https://arc.aiaa.org/doi/10.2514/6.2022-1834)
- [Indoor blimp dynamics and robust control, CERN magnetic environment (open access)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10611505/)
- [Review of autonomous outdoor blimps and their applications](https://cdnsciencepub.com/doi/full/10.1139/dsa-2023-0052)
- [PX4 Precision Landing](https://docs.px4.io/main/en/advanced_features/precland) · [ArduPilot IR-LOCK Precision Landing](https://ardupilot.org/copter/docs/precision-landing-irlock.html) · [IR-LOCK products](https://irlock.com/collections/precision-landing)
- [How DJI Dock 2 precision landing works (heliguy)](https://www.heliguy.com/blogs/knowledge-base/how-is-the-precision-landing-of-dji-dock-2-achieved/) · [DJI Dock 2 FAQ](https://enterprise.dji.com/dock-2/faq)
- [Regression-Based Docking for Mobile Robots using Monocular Camera + ArUco](https://pmc.ncbi.nlm.nih.gov/articles/PMC12196723/)
- [K&J D42 magnet specs](https://www.kjmagnetics.com/proddetail.asp?prod=D42) · [Adafruit 5V electromagnet P20/15](https://www.adafruit.com/product/3872) · [Adafruit Qi receiver module](https://www.adafruit.com/product/1901)
- [Docking systems for drones — patent landscape](https://xray.greyb.com/drones/docking-system-for-drones)

**Items not verified** (search budget exhausted; paywalls): AprilTag/ArUco pose precision at 1–2 m, spring-pin cycle-life datasheet numbers, Qi coil lateral-offset tolerance, and the full text (with measured landing accuracy) of the Auckland magnet-winch paper. None change the design recommendation, but the Auckland full text is worth institutional access before cutting metal.
