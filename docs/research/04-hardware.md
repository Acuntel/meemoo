# Research 04 — Hardware Feasibility (July 2026)

> Produced 2026-07-25 by the hardware research agent. Part of the Helpee
> pre-build research phase. See docs/RESEARCH.md for the synthesis.

**Headline verdict:** the aircraft is buildable, and near-silent flight comes free with buoyancy. But the honest minimum envelope is **~100–150 L (0.55–0.65 m sphere-equivalent)** — roughly 4–5× the founder's "two party balloons" (~28 L). The good news hidden in that: volume scales as the cube, so 4× the volume is only **1.6× the width** (0.39 m → 0.61 m). The mental image is much closer to achievable than the volume number suggests.

The real risk is not lift, size, or noise. It is **docking**: no one has published an autonomous micro-blimp-to-dock landing. That is simultaneously the biggest execution risk and the most defensible thing Helpee would own.

Also material and new: the **150 g payload target is overbuilt** — a realistic BOM comes in at ~49 g plus margin ≈ 65 g, which is what pulls the envelope down to ~100–120 L.

---

## A. Lift physics and size

### The math, explicitly

Net buoyancy of helium at 20 °C, sea level:

```
ρ_air (20°C)  = 1.204 g/L
ρ_He  (20°C)  = 0.166 g/L
gross lift     = 1.038 ≈ 1.04 g/L
```

**1.02 g/L** is the design figure (small derate for envelope overpressure and 99%-not-100% purity). Some papers use 1.11 g/L ([PUB](https://arxiv.org/pdf/2508.12395)) — that implies ~5 °C air and is optimistic for a heated home. Independent sources bracket 1.06 g/L ([Omnicalculator](https://www.omnicalculator.com/everyday-life/helium-balloons)).

**Critical derate:** party-store disposable tanks are now **80% helium / 20% air** because of the supply crisis ([Bargain Balloons](https://support.bargainballoons.com/support/solutions/articles/27000057685-does-my-helium-tank-contain-100-percent-helium-)). Mixture density = 0.8(0.166) + 0.2(1.204) = 0.374 g/L, so lift drops to **0.83 g/L — a 20% loss**. Helpee cannot use consumer tanks; it needs ≥99% balloon-grade gas.

Envelope surface area, for a 2:1 prolate ellipsoid (whale-shaped) with a 15% allowance for seams, valve, and fin patches:

```
A_eff = 4.836 · V^(2/3) · 1.077 · 1.15 ≈ 6.0 · V^(2/3)      [V in m³, A in m²]
payload = 1000·L·V − σ·A_eff
```

### Envelope self-weight (verified numbers)

| Material | Areal density | Source |
|---|---|---|
| 12 µm BoPET, plain | **16.7 g/m²** | [CloudFilm](https://www.cloudflexfilm.com/density-of-met-pet-film-weight-yield-buyer-guide/) — 1 m² of 12 µm MET PET = 16.68 g |
| Commercial mylar party balloon (nylon + metallized PET laminate) | **25–32 g/m²** | Derived from two real platforms, below |
| TPU-coated nylon (puncture-resistant) | 40–60 g/m² | [Textech](https://textechindustries.com/blog/airship-applications-polyurethane/), [DERFLEX](https://www.derflex.com/tpu-coated-nylon.html) |
| Latex | ~200 g/m² equivalent | Non-starter: 8–12 h float time ([Shimmer & Confetti](https://shimmerandconfetti.com/blogs/the-shimmer-and-confetti-blog/how-long-will-my-balloon-float-for-helium-float-times)) |

### Model validation against real platforms

**[PUB plasma blimp](https://arxiv.org/pdf/2508.12395)** (paper's Table 1): ellipsoidal aluminum-film balloon, 1.97 m long × 51 cm diameter, **V = 268.29 L**, envelope mass **measured at 79.36 g**, net available lift **218.44 g**. Back-solving gives σ = 79.36 / 2.49 m² = **31.9 g/m²**. Feeding 268 L and their own 1.11 g/L into the formula predicts **222.6 g** vs. their measured 218.4 g — **within 2%**.

**[Spinning Blimp](https://arxiv.org/html/2503.04112)**: 0.081 m³ mylar oblate spheroid, positive buoyancy **60 g**. Gross lift at 1.04 g/L = 84 g, so envelope ≈ 24 g over ~0.95 m² → **σ ≈ 25 g/m²**. Total BOM **$20**, including $0.78 for the mylar balloon and $0.24 of helium.

**[GT-MAB](https://www.freepatentsonline.com/y2019/0258257.html)** (patent, exact figures): saucer envelope **~0.7 m diameter, V ≈ 0.1805 m³**, mylar. Gondola **24.3 g without batteries**. Payload limit **<80 g** ([Zheng](https://justinyuzheng.wordpress.com/research-gtmab/)). Analog camera **4.5 g**. Endurance **>2 hours**. Five coreless thrusters, 31.8 ms time constant.

**[BlimpleBee](https://link.springer.com/chapter/10.1007/978-3-031-72062-8_16)** (Bristol, 2024): claimed smallest of its kind at **0.55 m diameter, 31.02 g** of vehicle hardware. Current published floor; maps to ~87 L.

**[Blimpduino 2](https://jjrobots.com/blimpduino-2/)** (open source): gondola ~33 g, control board 7.45 g, 300 mAh LiPo, 3 brushless motors, 45 mm props.

### The size table

Payload capacity vs. volume, three material/gas cases:

| Volume | Sphere-equiv. dia. | Whale (2:1) L × W | Payload @ σ=20, 1.02 g/L | Payload @ σ=30, 1.02 g/L | Payload @ σ=30, party gas |
|---|---|---|---|---|---|
| 28 L *(two balloons)* | 0.39 m | 0.61 × 0.31 m | **17.5 g** | 12.0 g | 6.7 g |
| 50 L | 0.47 m | 0.75 × 0.37 m | 34.7 g | 26.6 g | 17.1 g |
| 80 L | 0.55 m | 0.87 × 0.44 m | 59.3 g | 48.2 g | 33.1 g |
| **105 L** | **0.585 m** | **0.93 × 0.46 m** | **80.4 g** | **65.9 g** | **46.9 g** |
| **150 L** | **0.66 m** | **1.05 × 0.52 m** | **119.1 g** | **102.2 g** | **75.2 g** |
| 200 L | 0.72 m | 1.16 × 0.58 m | 163.0 g | 142.4 g | 104.4 g |
| 300 L | 0.83 m | 1.33 × 0.66 m | 252.2 g | 225.3 g | 168.3 g |

Inverting for payload targets:

| Payload target | Custom film (σ=20) | Commercial mylar (σ=30) |
|---|---|---|
| 65 g | **87 L** (0.55 m) | **102 L** (0.58 m) |
| 100 g | 128 L (0.63 m) | 147 L (0.65 m) |
| 150 g | 185 L (0.71 m) | 209 L (0.74 m) |
| 250 g | 297 L (0.83 m) | 330 L (0.86 m) |

### Verdict on size

**The 150 g payload target is overbuilt.** The BOM below comes in at **~49 g plus 30% margin ≈ 65 g** — consistent with GT-MAB's 24.3 g dry gondola and BlimpleBee's 31 g. So the target volume is **100–150 L**, not the 185–209 L that 150 g would demand.

**Recommended: ~120 L, whale-shaped, 0.95 m long × 0.48 m diameter** (0.61 m sphere-equivalent). Gives ~75 g payload on commercial mylar — 15% margin over the BOM.

**Is 28 L possible at any payload?** Not for this mission. It yields 17.5 g even with a custom 20 g/m² film. An absolute-floor stack (single custom PCB integrating ESP32-S3 + camera + mic + amp + IMU + ToF + motor drivers at ~2.5 g, three 4 mm motors, 150 mAh cell, motors bonded to the film with no gondola) lands at **14–18 g** — technically at the edge. But at that point flight rounds drop to 8–12 minutes, audio SPL falls below what a hard-of-hearing listener needs, and there is zero margin for docking hardware. **~60–80 L is the aggressive floor; 28 L is out.**

**What would have to be true to shrink below 60 L:** one custom PCB at ≤3 g replacing seven breakout boards, and accepting quiet audio plus 10-minute rounds. Measurable gate: build the PCB and weigh the stack. If flying mass excluding envelope is ≤20 g, 60 L opens up.

**Counter-argument worth taking seriously — bigger is better here.** A 300 L whale (0.66 × 1.33 m) is calmer in drafts (see D), fits a real speaker with a proper baffle, has the area budget for the plush puncture-resistant skin the founder actually wants, and reads as a *character* rather than a gadget. The "two balloons" instinct optimizes the wrong variable.

---

## B. Component weight budget

Realistic BOM for the dumb aircraft. Weights from vendor specs where found, comparable-part measurements otherwise.

| Item | Part | Mass | ~$ | Note |
|---|---|---|---|---|
| Compute + camera + mic | [XIAO ESP32S3 Sense](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/) (OV2640 + PDM mic, 21×17.5 mm) | 3.5 g | $14 | One board covers three functions |
| Speaker | 28 mm mylar, 8 Ω 1 W ([Taoglas](https://www.taoglas.com/product/28mm-round-miniature-speaker-1w/), [Misco 28RN08M](https://store.miscospeakers.com/1-1-inch-8-ohm-voice-range-speaker-28rn08m-1) voice-range) | 3.0 g | $2 | Heaviest single mission item |
| Speaker baffle | 3D-printed thin-wall | 2.0 g | $0.20 | Non-optional for intelligibility |
| Audio amp | MAX98357A I2S class-D | 1.0 g | $5 | 0.3 g as bare chip on custom PCB |
| Altimeter | VL53L1X ToF | 1.0 g | $8 | **Essential** — see note |
| IMU | 6-axis LSM6DSO / MPU6050 | 1.0 g | $5 | Swing damping + attitude |
| Motors | 4 × 6×14 mm coreless @ 2 g ([DFRobot](https://www.dfrobot.com/product-2308.html), 53k RPM) | 8.0 g | $6 | ~15 gf static thrust each |
| Props | 4 × 45 mm @ 0.4 g (Gemfan) | 1.6 g | $3 | |
| Motor drivers | 2 × DRV8833 dual H-bridge | 2.0 g | $6 | |
| Battery | 1S LiPo 300 mAh | 7.5 g | $6 | Sized below |
| Gondola frame | 3D-printed PLA / foam core | 8.0 g | $1 | |
| Wiring, connectors | | 4.0 g | $2 | |
| Dock interface | 2 charge pads + 2 N35 disc magnets + 3 IR photodiodes | 3.0 g | $3 | |
| Fins / tail | Depron, bonded to envelope | 4.0 g | $1 | Damping *and* the cute tail |
| **Subtotal** | | **49.6 g** | **~$62** | |
| Margin (30%) | | 14.9 g | | |
| **Design payload** | | **~65 g** | | → **~102 L** on commercial mylar |

**Two notes that matter more than the numbers:**

The **ToF altimeter is not optional**. The [blimp swarm paper](https://arxiv.org/pdf/2505.09511) states monocular depth estimation was too error-prone and they integrated a laser altimeter to measure altitude directly, "reducing reliance on depth estimation." They also warn: *"Without external positioning devices or a velocity sensor, direct velocity control for waypoint tracking is not feasible."* Plan for the altimeter and for outside-in position sensing from the start.

The **speaker is the binding mission constraint**. A 20 mm unit at 1.5 g exists but has no low end and no baffle volume. A 28 mm voice-range driver with a printed baffle (~5 g total) is the smallest thing producing speech an older adult will comfortably parse at 1–2 m. Small-speaker SPL runs ~78–80 dB at 1 m for 1 W; a 1S LiPo into 8 Ω through a bridge-tied class-D caps at ~0.85 W peak, so budget **~75 dB at 1 m** — adequate for the 65–70 dB needed at 1–2 m, but with little headroom. Do not shrink this item.

### Battery sizing / flight time

| Load | Current |
|---|---|
| ESP32-S3 + camera + continuous WiFi MJPEG | 200 mA |
| 4 coreless motors, ~30% throttle at ~40% duty | 160 mA |
| Audio (10% speech duty) | 25 mA |
| IMU + ToF | 25 mA |
| **Average** | **~410 mA (~1.5 W)** |

20 minutes needs 137 mAh; at 80% depth-of-discharge, **~171 mAh**, so a **300 mAh** cell (7.5 g) gives comfortable margin.

**The 10–20 minute round spec is easy — endurance is not a constraint.** GT-MAB achieves >2 hours because a neutrally-buoyant vehicle spends ~zero energy staying aloft. Helpee's budget is dominated by *video streaming*, not flight. 40–60 minutes is reachable; the real limiter is dock cycles, not battery.

### Radio + video link

ESP32-CAM MJPEG over WiFi is adequate. Real-world numbers: **QVGA at 8–15 fps** on a strong 2.4 GHz link within 5–10 m, "sufficient for driving control"; **VGA at 10–12 fps** for surveillance-grade identification; latency ~one frame period, **~100 ms at 10 fps**; bandwidth ~500 KB/s–1 MB/s at VGA ([Zbotic](https://zbotic.in/esp32-camera-streaming-mjpeg-video-to-browser-tutorial/), [ESP32-CAM benchmark](https://arxiv.org/html/2505.24081v1)). Optimized forks reach 34–44 fps at 50–80 ms ([esp32-cam-fpv](https://github.com/jeanlemotan/esp32-cam-fpv)).

10 fps monitoring plus command/control over WiFi to the base station is comfortably within spec. Streaming is the dominant power draw (~200 mA of ~410 mA total). Worth knowing: GT-MAB used a **4.5 g analog 5.8 GHz camera** — lighter and lower-latency than WiFi — but WiFi is the right call here because it carries the command channel for free and fits the dumb-aircraft/smart-base split.

---

## C. Docking recommendation

**This is the #1 risk and the founder is right to call it that.** The literature gap is stark: searching for blimp docking returns [quadrotors docking *onto* blimps](https://arxiv.org/html/2511.19135v1) (2025, first such demo outside simulation), not blimps docking to stations. The GT-MAB patent, exhaustive elsewhere, "lacks specifications for docking systems or charging procedures." **Nobody has done this.**

### Primary: three-layer, base-station-led

**Layer 1 — far field (0.5–5 m): outside-in tracking from the base station.** Two wide-FOV cameras on the dock with a 15–20 cm stereo baseline track 2–3 IR LED or retroreflective markers on the envelope. The base station computes blimp pose and radios velocity commands over WiFi.

Right choice because it fits the dumb-aircraft architecture exactly, costs **zero aircraft grams**, and sidesteps the monocular-depth problem — the base knows its own geometry from one-time setup calibration. It is also precisely what the GT-MAB patent already describes: a ground station receiving the blimp's video, detecting features, and generating control signals transmitted back. Proven for face-following at 1–2 m. The swarm paper's block diagram confirms the same split: onboard = laser altimeter + IMU + monocular camera + rotors; Ground PC = Kalman filter, visual detection, autonomous navigator, swing-reducer.

**Layer 2 — terminal (0–50 cm): IR beacon homing.** Base cameras lose the blimp as it descends into the funnel (occlusion plus extreme foreshortening). Hand off to 3–4 IR LEDs on the funnel rim read by 3 photodiodes on the blimp's belly. This is the [AIRA](https://arxiv.org/html/2407.05619) approach — IR bulb at the landing station plus a 3-photodiode array on the drone, designed explicitly for palm-size microdrones with low battery life, working in complete darkness and partial non-line-of-sight. Adds ~0.5 g. Immune to room lighting; a camera is not. ([IR-LOCK](https://ardupilot.org/copter/docs/precision-landing-irlock.html) is the mature commercial equivalent.)

**Layer 3 — capture: funnel + magnet + pogo pins.** A cone with ~30–40° walls gives gravity self-centering; [proven for quadrotors](https://www.mdpi.com/2504-446X/6/3/56) where "even if drone legs land on the side of the station, the angle of the legs allows the drone to manoeuvre into the cone." A permanent magnet pair (N35 disc on the belly, steel plate in the throat) snaps the last 5–10 mm and holds with zero power. Two spring pogo pins in the throat make the charge contact — [>100,000 cycle life](https://cfeconn.com/pogo-pin-magnetic-connectors-in-robotic-systems/).

**Skip Qi wireless.** Receiver coils run [5–9 g](https://www.adafruit.com/product/1901) — 8–14% of the entire payload — to solve a problem two pogo pins solve for 1 g.

### Fallback: AprilTag on the dock, detected base-side

Put a fiducial on the dock and detect it in the blimp's own OV2640 stream — but run the detector *on the base station*, which already has the video. **Costs zero extra grams and zero extra dollars.** [AprilTag is the standard choice](https://automaticaddison.com/autonomous-docking-with-apriltags-using-nav2-ros-2-jazzy/) for exactly this. It is the fallback rather than the primary because OV2640 rolling shutter at 10 fps plus ~100 ms WiFi latency makes visual servoing sluggish — though the blimp's slow dynamics may well tolerate it. **Build both; the marginal cost is a few hundred lines of code.**

### How does a neutrally-buoyant vehicle land and stay?

| Approach | Verdict |
|---|---|
| Ballonet + air pump (real airships — [HowStuffWorks](https://science.howstuffworks.com/transport/flight/modern/blimp.htm)) | **Dead end at this scale.** Pump + valve + plumbing is 10–20 g minimum |
| Drop water/sand ballast | Dead end — irreversible, needs refill |
| Continuous downward thrust to hold | Bad — burns power exactly while charging, and makes noise next to where the user sits |
| **Trim slightly heavy + magnet capture** | **This is the answer** |

**Trim the blimp 2–4 g negatively buoyant.** Flight then uses the two vertical thrusters for altitude hold via PID on the laser altimeter — what GT-MAB and the swarm blimps already do. Landing becomes "stop thrusting and steer." Descent is passive and gentle. On contact, 2–4 g of negative trim plus a ~8–12 gf magnet gives a firm zero-power hold; takeoff spins up the vertical thrusters (2 × 15 gf = 30 gf available) to break it.

**This is also the critical safety decision.** A *positively* buoyant blimp that loses power parks itself on the ceiling and someone needs a broom — unacceptable for an 80-year-old living alone. Negative trim makes power loss a slow, gentle descent to the floor. **Ship it negative.**

**Then put a load cell in the dock.** For ~$3, the base station weighs the blimp on every docking and knows its exact trim state. That converts the worst UX problem in the product — invisible, gradual helium loss — into an instrumented one with a specific instruction: "add one washer" or "Helpee needs a top-up." Strongly recommended.

---

## D. Noise verdict

**Near-silent is achievable, and it is a gift of physics rather than a clever trick.**

A 150 g quadcopter must generate 150 gf ≈ 1.47 N of thrust *continuously* just to stay up. A neutrally-buoyant Helpee needs **zero** thrust to hover, and only ~1–3 gf (10–30 mN) for gentle translation and draft rejection. That is a **50–150× reduction in required thrust**, achieved by running the same-size props at roughly 20–30% of quadcopter RPM.

Propeller noise is brutally sensitive to tip speed. [AIAA](https://arc.aiaa.org/doi/10.2514/1.C035242) reports **9 dB from an 11% RPM cut** (2700→2400). A conservative 50·log₁₀(RPM ratio) scaling for a 3× RPM reduction gives **~24 dB**.

Baseline: mini/toy drones measure **50–65 dB at 1 m** ([DronesGator](https://dronesgator.com/how-loud-are-drones)). Subtract 20–25 dB → **~35–45 dB at 1 m**, at or below quiet-home ambient (30–40 dB). Audible as a faint whir with your ear near it; inaudible across a room.

**Honesty flag: no published dB measurement exists for any micro blimp.** The number above is derived, not measured. Confirm it with a $30 SPL meter on the first prototype — a one-hour test.

### How to actually achieve it

1. **Large, slow props.** 45–50 mm at low RPM, 3+ blades. [High blade count with lower RPM is the standard low-noise approach.](https://www.sciencedirect.com/science/article/abs/pii/S1270963823002481)
2. **Soft-mount every motor.** The non-obvious one and the real risk. The envelope is a ~2 m² thin-film membrane — a drumhead. Any structure-borne motor vibration coupled into it turns the whole blimp into a loudspeaker. Use foam grommets, and **never bond motors rigidly to the envelope film.** Aerodynamic noise is already solved; structural buzz is what will bite.
3. **Tune for spectrum, not just level.** Human hearing peaks at 2–5 kHz, exactly where prop tip noise lives, and [a 65 dB low hum is less annoying than a 62 dB high whine](https://dronesgator.com/how-loud-are-drones). Bias toward larger/slower.

### Exotic propulsion: don't

**Plasma / ionic thrust — no.** [PUB](https://arxiv.org/pdf/2508.12395) needed **27 kV** to fly a 268 L blimp, with a 33 g gimbal and a 42.5 g battery. High voltage in a home, near an older adult, near a helium envelope, plus corona-generated ozone, plus a mass budget it blows twice over. Hard no for a consumer product. (Standalone ion drones are 2.5 kg / 70 cm at 40 kV for ~4.5 min — [New Atlas](https://newatlas.com/drones/undefined-ion-propulsion-drone/).)

**Flapping fins — no.** Festo's platforms don't scale down: [AirJelly](https://www.festo.com/us/en/e/about-festo/research-and-development/bionic-learning-network/bionic-flying-objects/airjelly-id_33841/) is 1.3 kg at 1.35 m; AirPenguin is 3.7 m with ~1 m³ of helium for ~1 kg of lift. The closest scale-appropriate work — [insect-sized flapping thrusters](https://www.sciencedirect.com/science/article/pii/S1000936124000311), 80 mg each, 3.5 cm wingspan, on a 23 cm blimp — runs at **80 Hz**, an audible hum, and produces trivial thrust.

**Conventional slow coreless props win. The requirement is already met; don't chase exotica.**

### Indoor air currents

The dominant disturbance, and researchers report it honestly. The [Spinning Blimp](https://arxiv.org/html/2503.04112) paper is the cleanest data point: the long-wing (1.3 m) variant showed "resilience from constant wind velocity up to v = 0.5–1.5 m/s," while the short-wing (0.7 m) version "showed minimal resilience to constant and gusting wind conditions." [HVAC fans dominate a building's air movement](https://buildingscience.com/documents/digests/bsd-014-air-flow-control-in-buildings), and duct imbalance can raise infiltration by up to 300%.

Why **bigger is calmer** — the counterintuitive result:

```
Disturbance force F = ½ρ·Cd·A·v²   at v = 0.3 m/s, Cd = 0.47
  28 L  (r=0.19 m): F = 3.0 mN   effective mass ≈ 50 g  → a = 0.059 m/s²
 200 L  (r=0.36 m): F = 10.5 mN  effective mass ≈ 361 g → a = 0.029 m/s²
```

(Effective mass ≈ 1.5× displaced air, including added-mass.) The force *ratio* to available thrust is roughly size-independent, but the small blimp **accelerates twice as fast** under the same draft — it gets shoved around more and is harder to control. Matches the Spinning Blimp result exactly. Another reason not to chase 28 L.

---

## E. Helium economics

### Leak rate

Best measured figure found: a 91 cm commercial mylar balloon lost **0.35 g of lift per day** ([Self-Sustainability in Nano UAVs](https://www.researchgate.net/publication/317394151_Self-Sustainability_in_Nano_Unmanned_Aerial_Vehicles_A_Blimp_Case_Study)), with the authors concluding that over battery-relevant timescales "helium lift can be assumed to be constant." Metallized PET is a genuinely good barrier — [permeability ≈ 4.1% of uncoated PET](https://www.sciencedirect.com/science/article/abs/pii/S0017931012007077).

Scaling by area to a 120 L envelope (~2.0 m²) gives roughly **0.2–0.3 g/day through the film**. Add valve and seam losses — call it **0.3–0.6 g/day** real-world.

**The binding constraint is trim tolerance, not deflation.** The envelope stays visibly full for weeks (foil balloons stay "full and taut 3–5 days and float two weeks or longer" — [Shimmer & Confetti](https://shimmerandconfetti.com/blogs/the-shimmer-and-confetti-blog/how-long-will-my-balloon-float-for-helium-float-times); Air Swimmers claims [two weeks per refill](https://www.walmart.com/ip/Air-Swimmers-Remote-Control-Flying-Shark/19512514); advertising blimps [3–10 days](https://www.mobileairships.com/repairsheliumwarranty)), but a vehicle trimmed to ±3–5 g goes out of trim long before it looks soft.

**Realistic re-trim cadence: every 1–3 weeks.**

### Cost

| Source | $/L | 120 L initial fill | Notes |
|---|---|---|---|
| 50 ft³ (1416 L) refillable cylinder, ~$115 | $0.081 | **$9.75** | ~$2.30/ft³ ([Bhumi](https://bhumicalculator.com/countries/united-states/helium-cost-per-cubic-foot)) |
| Balloon Time 14.9 ft³ (422 L), $52.47 | $0.124 | $14.90 | **Unusable — 80/20 He/air, and non-refillable** |

Monthly top-off at ~0.3 g/day ≈ **9 L of helium ≈ $0.73/month.** Even at 3× post-Qatar prices, **~$2.20/month.**

### Subscription viability

**Helium cost is not the problem — roughly $10–25/year per unit in gas. The problem is user action.** An 80-year-old will not source balloon-grade helium and hand-trim a robot every two weeks. So the subscription should sell *logistics*, not gas.

**The compelling version: a dock-integrated helium cartridge with automatic top-off.** A 2 L cylinder at 200 bar holds ~400 L STP — at 9 L/month that is **over three years of top-offs**. Pair it with the dock load cell: the dock weighs the blimp, detects trim drift, and opens a solenoid valve against the envelope's fill port while docked. This eliminates the single worst UX problem in the product, makes the subscription concrete (cartridge replacement), and is mechanically simple. **Treat this as a core feature, not an accessory.**

### Envelope material and the malleability wish

"Puncture-resistant but slightly malleable" = a **bladder-in-shell** design: an inner metallized-BoPET gas bladder for the barrier, inside an outer soft shell (knit spandex or brushed TPU-coated nylon) carrying abrasion duty, whale graphics, and soft-touch feel. TPU-coated nylon has [excellent abrasion and puncture resistance and heat-welds to itself at ~200 °C](https://erez-therm.com/tpu-coated-fabric-definitive-guide-durability-safety-uses/).

The arithmetic is unforgiving. At 120 L (~2.2 m² with allowance): bladder 40 g + a 50 g/m² outer shell at 110 g = **150 g of envelope** against a 75 g payload budget. It does not close.

**So pick one, deliberately:**

- **(a) 100–150 L, single-layer film.** Accept shiny-and-delicate; protect only the lower third with a soft printed sleeve where hands touch. *Recommended for the prototype.*
- **(b) 250–300 L, full bladder-in-shell.** The plush, malleable, puncture-tolerant skin — and at 0.66 × 1.33 m it's a ceiling-height pet, not a vehicle. *This is the version people will actually love.*

### Supply risk

**Changed materially in the last four months.** Iranian missile strikes on Ras Laffan on 18–19 March 2026 took Qatari helium production offline; Qatar is [~30% of global supply](https://www.exiger.com/perspectives/iran-war-disrupts-one-third-of-global-helium-supply/), with global-hit estimates ranging from [11%](https://www.agbi.com/industry/2026/03/qatari-lng-shutdown-puts-11-of-global-helium-supply-at-risk/) to a third. Spot prices rose **40%** per Bank of America, with [some markets up 70–100% within a week](https://cen.acs.org/business/specialty-chemicals/Iran-war-threatening-global-helium/104/web/2026/03). Baseline forecasts already called for [5–8% annual increases](https://bhumicalculator.com/countries/united-states/helium-cost-per-cubic-foot). Helium has no substitute and semiconductors outbid balloons ([Fortune](https://fortune.com/2026/03/21/iran-war-helium-shortage-qatar-chip-supply-chains-ai-boom/)).

The reassuring part: at 9 L/month per unit, **even a 5× price shock keeps annual gas cost under $50/unit.** The exposure is availability and optics ("helium shortage" headlines while shipping a helium product), not unit economics. Contract balloon-grade supply early.

---

## F. Bump recovery

**Pitch and roll recovery is free and reliable. Yaw and translation are not.**

Hanging the gondola below the center of buoyancy creates passive pendulum stability — [the center of mass at the bottom "creates a pendulum-like behavior that naturally maintains its horizontal attitude passively."](https://arxiv.org/html/2503.04112) With 65 g at 0.15 m below the CB, the restoring moment at 10° of tilt:

```
τ = m·g·d·sin(θ) = 0.065 × 9.81 × 0.15 × sin(10°) = 16.6 mN·m
```

A strong, unconditional restoring torque. It *will* self-right.

**The problem is that a pendulum is undamped — it oscillates.** This is the known open problem in the field: there is a paper titled [Modeling and Control of Swing Oscillation of Underactuated Indoor Miniature Autonomous Blimps](https://www.worldscientific.com/doi/abs/10.1142/S2301385021500060), GT-MAB's stated research goal is ["constant forward and sideway velocity with reduced oscillation"](https://www.gtsr.gatech.edu/gtsr-research/gt-mab/), and the [swarm paper's](https://arxiv.org/pdf/2505.09511) actuation layer contains a dedicated **"Swing-Reducer"** block alongside the thrust mixer.

Recommended stack, in order of leverage:

1. **Passive pendulum** for pitch/roll. Free. Longer arm = stronger restoring, slower oscillation.
2. **Fins and a tail** for aerodynamic damping in translation and yaw (~4 g of Depron). Form and function align — the whale's tail is the damper.
3. **Active swing damping.** IMU measures pitch rate; the base station commands counter-thrust phased against the swing. Implement the published Swing-Reducer. (Balloon-gondola literature also shows [reaction wheels recover coupled pendulum-torsion stability](https://www.sciencedirect.com/science/article/abs/pii/S1270963821001176), but that's mass you don't have.)
4. **Yaw needs active control unconditionally** — no passive restoring moment about the vertical axis.

**The latency question resolves favorably.** A 0.15 m pendulum has a ~0.78 s natural period, stretched to 1.5–3 s by added-mass effects on a buoyant body. Against that, ~100 ms of WiFi round-trip is negligible. **Slow dynamics is the gift of this platform** — it is why offboard control works here and would not work on a quadcopter.

**The genuinely hard part is the sequel, not the bump.** After a bump the blimp has drifted 0.5–1.5 m with no position reference and no restoring force in translation. This is exactly where the base-station camera earns its keep — it is the only sensor that can say "you are 1.2 m left of where you were."

Worth noting for the product story: GT-MAB is explicitly designed so it ["is safe while flying in close proximity to humans"](https://www.gtsr.gatech.edu/gtsr-research/gt-mab/), and the HRI literature frames blimps as offering [enhanced safety and endurance in human-centered spaces where quadcopters fail](https://www.researchgate.net/publication/330981024_Autonomous_flying_blimp_interaction_with_human_in_an_indoor_space). The soft-envelope collision tolerance is a real, citable advantage for the older-adult use case.

---

## G. Top 5 hardware risks

### 1. Autonomous micro-blimp docking has never been demonstrated — CRITICAL

Published blimp-docking work is [quadrotors landing *onto* blimps](https://arxiv.org/html/2511.19135v1); the GT-MAB patent has nothing on docking or charging. Helpee would be first. That is the risk *and* the moat.

**What would have to be true:** base-station outside-in tracking holds <5 cm lateral accuracy at 1 m from the dock; IR terminal homing closes the last 30 cm to <3 cm; and the funnel capture radius is ≥8 cm so tolerances stack with margin.
**How we'd know:** 100 docking attempts from randomized start poses within 3 m. Target >95% first-attempt, >99.5% with one retry. Prove it in the simulator first, then on a tethered rig before free flight.

### 2. Envelope size lands at ~4× the founder's target — HIGH (largely retired by reframing)

100–150 L is the honest floor; 28 L yields 17.5 g of payload against a 49 g BOM.

**What would have to be true to reach 60 L:** one custom PCB integrating everything at ≤3 g, three 4 mm motors, a 150 mAh cell, motors bonded to the film with no gondola — and accepting ~10-minute rounds plus quieter audio.
**How we'd know:** build the PCB and weigh the stack. ≤20 g flying mass excluding envelope opens 60 L.
**Reframe that mostly retires this:** 4× the volume is only 1.6× the width (0.39 → 0.61 m). And bigger is *calmer*. The size target is fighting the product's own interests.

### 3. Helium trim drift is recurring maintenance on the least suitable user — HIGH

0.3–0.6 g/day of lift loss against a ±3–5 g trim budget means re-trim every 1–3 weeks, forever, by someone who may be 85.

**What would have to be true:** the dock instruments trim automatically (load cell) and either reduces the interaction to "add one washer" or eliminates it via dock-integrated cartridge auto-top-off.
**How we'd know:** instrument a prototype envelope for 60 days, plot lift vs. time. Target <0.25 g/day and a ≥21-day re-trim interval. Then validate the dock's trim measurement against a bench scale to ±0.5 g.
This is the risk most likely to kill the product quietly through churn, and also the one with the cleanest engineering fix.

### 4. Helium supply and price volatility — MEDIUM

Qatar offline since March 2026; spot up 40–100%; no substitute; semiconductors outbid balloons. Party-store tanks are now 80/20 He/air and cost 20% of lift.

**What would have to be true:** contracted balloon-grade (≥99%) supply, and a re-trim cadence ≥3 weeks so annual consumption stays near 100 L/unit/year.
**How we'd know:** model annual per-unit helium cost under a 5× price shock. Under $50/yr it's a rounding error at companion-robot pricing — which the numbers say it is. Manage as procurement and messaging, not economics.

### 5. Draft rejection and the "it wandered into the kitchen" failure — MEDIUM

The 0.7 m Spinning Blimp "showed minimal resilience to constant and gusting wind conditions." Homes have HVAC registers, open doors, and ceiling fans.

**What would have to be true:** station-keeping within a 0.5 m box against a 0.3 m/s draft, plus a geofence and a recovery behavior for lost tracking.
**How we'd know:** station-keeping RMS error with a box fan at 0.3 and 0.5 m/s from 2 m; plus lost-and-recovered success rate.
**Mitigation is cheap and already implied by the architecture:** the base station knows where the blimp is, so "drifted out of the tracked volume" is *detectable*. The response is a scripted "climb to a known height, yaw-scan for the dock's IR beacon, come home."

**Honorable mentions:** speaker SPL adequacy for presbycusic listeners (test with real users early — a 3 g decision with outsized UX impact); envelope puncture from pets and grandchildren; and the ceiling-parking failure mode, which negative trim retires for free.

---

## What to do next

1. **Build the docking loop in the simulator now**, since that's where the software already is. Model the funnel geometry, the IR beacon's angular response, and ~100 ms of command latency. Docking is the risk that can't be bought off with money or grams.
2. **Buy a 36-inch mylar balloon, a XIAO ESP32S3 Sense, four coreless motors, and a $30 SPL meter.** For under $80 the noise estimate and real leak rate can be validated within a week — the two numbers in this report that are derived rather than measured.
3. **Put the load cell in the dock from v1.** It's $3 and converts the product's worst structural UX problem into a solved one.

The physics is on this project's side. Buoyancy gives near-silent flight, two-hour endurance potential, and inherent safety around frail users — none of which a quadcopter can offer at any price. The size wish needs to move, and docking is genuinely unsolved research. Everything else is engineering.

---

### Note on research completeness

The session-wide WebSearch cap (200 calls) was hit at the end. Two component weights in the BOM are estimates from comparable parts rather than confirmed vendor specs: the XIAO ESP32S3 Sense (3.5 g — dimensions confirmed at 21×17.5 mm, weight not published) and the VL53L1X ToF breakout (1.0 g). Neither changes any conclusion; combined they are ~4.5 g of a 65 g budget. Two paywalls: the BlimpleBee full paper (Springer) and the Georgia Tech thesis (403) — but the GT-MAB patent gave the same numbers more precisely.
