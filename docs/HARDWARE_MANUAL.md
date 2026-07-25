# Meemoo Hardware Manual — for someone who has never built hardware

> Written 2026-07-25 for Brady. Zero experience assumed. Every term is defined
> the first time it's used, and the important ones twice. Read top to bottom
> once before ordering anything. Companion docs: ORDER_LIST.md (what to buy),
> build-steps/step-09.md (the experiments), BUILD_PLAN.md (how it all connects).

---

## 0. Safety first (read this twice)

- **LiPo batteries can catch fire if abused.** A LiPo (lithium-polymer battery —
  the small flat rechargeable battery that powers drones and our blimp) is safe
  if you: never puncture it, never charge it unattended, never charge a puffy or
  damaged one, and charge it inside a fireproof "LiPo bag" ($8, buy one). Ours
  is tiny (300 mAh — about 1/40th of a phone battery), which limits how bad any
  failure can be. Still: charge on a hard surface, in the bag, while you're home.
- **Helium is not flammable** (that was hydrogen, and the Hindenburg). Helium is
  completely inert — it cannot burn or explode. The only risk is asphyxiation if
  you dump a huge amount into a tiny sealed room, which our volumes can't do.
  Don't inhale it for the funny voice; it displaces oxygen in your lungs.
- **Magnets**: the small neodymium discs we use snap together hard enough to
  pinch skin and they kill credit cards/hard drives at close range. Keep them
  away from your laptop.
- **Soldering** (melting metal to join wires — see §2): the iron tip is ~350 °C.
  Hold it like a pen, never grab the metal end, work in a ventilated room.

## 1. The big picture — what we're building on the bench

The finished Meemoo has three physical parts. The bench phase builds crude
versions of each to answer questions BEFORE we spend money on custom parts:

1. **The aircraft** — for now, a 36-inch (91 cm) round mylar balloon with a tiny
   circuit board and motors taped to it. It answers: how loud? how leaky? can
   it be caught by a cone?
2. **The dock** — for now, a foam-board cone with an electromagnet at the back.
   It answers: does a floating balloon self-center into a cone, or do we need a
   motorized winch to pull it in?
3. **The base station** — your Mac running the `meemoo` software. It's already
   real; the bench connects to it over WiFi.

## 2. Glossary (the words that will come up constantly)

- **Breakout board**: a chip mounted on a small ready-made circuit board with
  easy connection points, so beginners don't need to design electronics. Almost
  everything we buy is a breakout board.
- **Microcontroller (MCU)**: a tiny computer-on-a-chip. Ours is the **ESP32-S3**
  — think "a $14 computer the size of a stamp that has WiFi."
- **XIAO ESP32S3 Sense**: the exact board we use — an ESP32-S3 that ALSO has a
  camera and microphone already attached. One purchase = the aircraft's brain,
  eye, and ear.
- **Firmware**: the program that runs ON the microcontroller (as opposed to
  software, which runs on your Mac). You upload ("flash") firmware to the board
  over a USB-C cable. Our repo will contain the firmware; flashing is
  one command.
- **Soldering**: joining wires/pins by melting a soft metal (solder) over the
  joint with a hot iron. You will need to do a little of this (motor wires).
  Watch one 10-minute YouTube basics video first; practice on spare wire. Buy:
  a $25 soldering kit (iron, solder, stand, brass sponge).
- **Coreless motor**: the tiny cylindrical motor used in mini-drones. Two thin
  wires come out; power makes it spin; reversing polarity reverses direction.
- **H-bridge / motor driver (DRV8833)**: a breakout board that lets the
  microcontroller control motor speed and direction. (An MCU pin can't power a
  motor directly — the driver is the muscle between brain and motor.)
- **PWM**: how the MCU sets motor speed — switching power on/off thousands of
  times per second; more "on" time = faster spin. You never handle this
  directly; the firmware does.
- **I2C / I2S**: two standard ways chips talk over a few shared wires. I2C =
  sensors (our distance sensor + motion sensor). I2S = digital audio (our
  microphone/speaker amp). You just connect the labeled pins; the firmware
  speaks the protocol.
- **ToF sensor (VL53L1X)**: "time-of-flight" — a tiny laser rangefinder that
  measures distance (for us: height above the floor) by timing light bounce.
- **IMU (MPU6050)**: "inertial measurement unit" — senses tilt and rotation,
  like the chip that rotates your phone screen. It's how Meemoo knows it's
  swinging after a bump.
- **SPL meter**: a sound-level meter, measures loudness in dB. $30 on Amazon.
- **Buoyancy / trim**: helium pulls up, weight pulls down. "Neutral trim" =
  perfectly balanced, floats in place. We deliberately trim 2–4 grams HEAVY so
  a dead battery means a slow gentle descent, never a balloon stuck on the
  ceiling.
- **Mylar (BoPET)**: the shiny metallic balloon film. Holds helium far better
  than latex (weeks vs hours) and is latex-free (hospital requirement, already).

## 3. Exactly what to buy, and where

Full table with prices in ORDER_LIST.md. Where to buy, by store:

| Store | Buy there | Why |
|---|---|---|
| **Amazon** | 36" round mylar balloons, digital 0.1 g scale, SPL meter, foam board, clay, LiPo bag, soldering kit, magnet discs, 5 V USB power supply, USB webcam | Fast, cheap, fine quality for bench work |
| **Seeed Studio (seeedstudio.com) or Amazon** | XIAO ESP32S3 Sense ×2 | The official maker; Amazon carries it marked up slightly |
| **Adafruit (adafruit.com)** | Electromagnet (product 3872), MAX98357A amp, DRV8833 drivers, VL53L1X, MPU6050 (or Amazon equivalents), pogo pins, IR LED kit | The beginner-friendliest electronics shop; every product page has a wiring guide — USE those guides |
| **DFRobot or Amazon** | 6×14 mm coreless motors, 45 mm props | Drone-parts commodity |
| **Airgas / Linde / local welding-gas supplier** (call first) | **Balloon-grade helium ≥99%**, smallest cylinder + a balloon-fill regulator | ⚠️ The one thing NOT to buy at a party store or Amazon: "Balloon Time" tanks are now 80% helium / 20% air — a secret 20% lift cut that ruins every measurement. Say to the supplier: "smallest cylinder of balloon-grade helium, at least 99%, with a balloon filling valve." ~$60–115 with cylinder deposit |

Optional but recommended: any cheap **kitchen scale** you already own (for
magnet-force measurement), painter's tape, fishing line (tethers).

## 4. How it all connects (the wiring, conceptually)

The bench aircraft, in plain words — each arrow is 2–4 soldered or plugged wires,
and every breakout's product page shows the exact pins:

```
LiPo battery → power switch → XIAO ESP32S3 Sense (brain+camera+mic)
                                    ├─ I2C → VL53L1X (height) + MPU6050 (tilt)
                                    ├─ I2S → MAX98357A amp → 28 mm speaker
                                    └─ GPIO pins → DRV8833 #1 → motors 1+2 (vertical props)
                                                 → DRV8833 #2 → motors 3+4 (forward/steer props)
```

- The XIAO's built-in camera streams MJPEG video over WiFi to your Mac; the Mac
  sends motor commands back over the same WiFi. That's the "dumb aircraft,
  smart ground" idea physically: the balloon carries eyes and muscles, your Mac
  is the brain.
- The **dock** is even simpler: foam cone + electromagnet wired through a MOSFET
  module (an electronic switch) to a 5 V USB supply; the webcam watches the
  approach; both plug into the Mac.
- Nothing on the aircraft is decision-making. If the WiFi drops, firmware's only
  job is: stop motors → drift gently down (negative trim catches it).

## 5. How each bench test actually works (step-by-step)

### Test 1 — Noise (1 hour, do first, no balloon needed)
1. Solder ~10 cm wires to one motor (your first soldering — it's two joints).
2. Wire motor → DRV8833 → XIAO per Adafruit's DRV8833 guide.
3. Flash the bench firmware (repo will provide `make flash-bench`) — it spins
   the motor at 20/30/50% in a loop.
4. Put the SPL meter 1 m away, room quiet, phone on airplane. Read dBA at each
   speed. Write numbers into `docs/bench-results.md`.
5. Pass = ≤45 dB at the speeds a blimp actually uses (20–30%). For reference: a
   quiet library is ~40 dB.

### Test 2 — Leak rate (5 min/day for 2 weeks)
1. Fill one 36" balloon with helium. Tie/clip it sealed.
2. Tape a small clay blob underneath until it *barely* floats up (≈5 g positive:
   it should rise slowly, like a lazy bubble).
3. Each day: tie it to the 0.1 g scale via light thread, read how hard it pulls
   up (the scale shows negative grams), write it down with the date.
4. The daily change IS the leak rate. Pass = ≤0.6 g/day. This number goes
   straight into the simulator as the trim-drift constant.

### Test 3 — Capture cone (the big one — 20 minutes once built)
1. Build a cone from foam board: mouth ~40 cm across, narrowing to a ~12 cm
   throat over ~35 cm depth. Hot glue. Ugly is fine.
2. Mount the electromagnet at the throat, facing out, wired through the MOSFET
   to USB power with a manual switch.
3. Trim a balloon EXACTLY neutral (add/remove clay until it hangs motionless).
   Tape a plastic bottle-cap "nose" with a steel washer on the front.
4. HVAC off. Hand-push the balloon nose-first toward the cone at a slow walk
   pace, releasing it ~50 cm out, at increasing sideways offsets (0, 5, 10,
   15 cm).
5. Watch: does the cone wall GUIDE the nose to the throat (where the magnet
   snaps it) — or does the balloon just stop dead against the wall?
6. Record the largest offset that still captures, at each speed.
7. **This single observation decides the dock design**: reliable centering →
   the simple cone dock wins; stalling → we build the motorized winch that
   reels it in (research/06 §E — also proven prior art, just one more part).

### Test 4 — Magnet hold & release (overnight)
Docked balloon on the (powered) magnet overnight, HVAC running normally. Morning
check: still docked? Flip the switch: does it release instantly, or does
leftover magnetism hold it? Measure any leftover pull by pulling with the
kitchen-scale hook. If sticky, the firmware fix is a brief reversed pulse —
note it either way.

### Test 5 — Dock camera tracking (with the step-06 software)
Hang a balloon on fishing line from a broomstick; move it slowly through the
webcam's view while `make track-bench` runs. The screen shows the computed
position; wave it at known distances and compare. Repeat in daylight, lamp
light, and near-dark. Pass = smooth 20 Hz tracking, ~1 cm accuracy at 1–2 m.

### Test 6 — Speaker intelligibility
Play Meemoo's actual TTS voice through the 28 mm speaker + amp at 1–2 m. Can
you understand every word across the room? Can a grandparent? If it's too
quiet, the fix list is: printed baffle (a small 3D-printed enclosure that
stops sound short-circuiting around the speaker), then a 2nd speaker, then
accepting closer conversation distance.

## 6. Where hardware meets the software

Every test plugs into code that already exists by the time you run it:

| Bench item | Software it connects to | The connection |
|---|---|---|
| XIAO camera stream | Perception's `VideoSource("mjpeg_url")` | paste the stream URL into config — the SAME pipeline that watched your webcam now watches the balloon |
| XIAO mic/speaker | Voice module's satellite transport | the aircraft becomes a wireless microphone/speaker for the same STT/TTS loop |
| Motors | `FlightController` — the `MqttBlimp` implementation replacing `SimulatedBlimp` | same interface, real thrust; the sim-tuned controller is the starting point |
| Cone + magnet + webcam | `DockController` + the step-06 docking state machine | the tracking loop that guided the sim whale guides the real balloon |
| Leak measurements | Sim constants + the dock load-cell trim logic | measured reality replaces estimates |

That's the whole "only the drivers get swapped" promise made physical: every
bench part slots into an interface the software already defines.

## 7. Wings — how Meemoo steers (Brady's question, answered)

Short version (full analysis: BUILD_PLAN §2): **propellers fly it, wings shape
it.** Four tiny slow-spinning props (near-silent at blimp thrust levels — that's
Test 1) do the actual steering: two pointed up/down for altitude, two pointed
forward/back for movement and turning, all commanded by your Mac. The
wing-shaped soft fins on the body are real aerodynamics — they damp the
swinging-pendulum wobble after a bump — and they're the character's fins/tail.
Later, tiny servos can slowly flap them for *expression* while the props keep
doing the precise work. Flapping wings as the actual engine (like the
Cuddle-Fish research robot) are silent but too weak and imprecise to hit a
docking cone — wrong tool for a robot that must land itself, right tool for
looking alive. An internal moving weight (silent pitch control) is a v2
experiment.

## 8. What you'll be able to do when the bench phase is done

- Quote a MEASURED noise figure and leak rate instead of estimates.
- Know whether the dock is a cone or a winch — the last big hardware unknown.
- Fly nothing yet — free flight waits for the sim-tuned controller (step 06)
  plus a tethered test. The bench phase deliberately contains zero crashes.
- Hand any engineer `docs/bench-results.md` and the repo, and they'd nod.
