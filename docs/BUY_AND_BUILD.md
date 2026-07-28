# Meemoo: Buy and Build, the Absolute Dummy Manual

> Written 2026-07-27 for Brady. Zero experience assumed. This is the full path
> from cardboard box to a robot flying around your room. Every link below was
> verified live on 2026-07-27. Photograph every stage as you build and Claude
> will embed the photos here, turning this into the real picture manual.
> Companion docs: HARDWARE_MANUAL.md (deeper explanations), ORDER_LIST.md
> (bench-test framing), build-steps/step-09.md (the experiments).

## Three safety rules, before anything

1. The battery charges inside the fireproof bag, on the counter, while you are
   home. Never puncture it.
2. The soldering iron's metal end is 350 C. Hold it like a pen, rest it in its
   stand, never on the desk.
3. Helium is safe (it cannot burn). Just don't huff it.

---

## Part 1: the shopping list (~$235 + helium)

Two strategies: the Amazon cart arrives in 1-2 days (~$235 total). Swapping
motors/battery/sensors to AliExpress saves ~$35 but takes 2-4 weeks.
Recommendation: Amazon. Speed beats $35 while prototyping.

### Box A: the flying electronics (~$95)

| # | Item | Why | Where | ~$ |
|---|------|-----|-------|----|
| 1 | Seeed XIAO ESP32S3 Sense, x2 | Brain + camera + mic in one stamp-sized board; one spare | [seeedstudio.com](https://www.seeedstudio.com/XIAO-ESP32S3-Sense-p-5639.html) ($13.99) or [Amazon](https://www.amazon.com/s?k=seeed+xiao+esp32s3+sense) | 28 |
| 2 | 8520 coreless motors 4-pack with props | The four muscles (standard mini-drone part) | [Amazon](https://www.amazon.com/s?k=8520+coreless+motor+with+propeller) | 12 |
| 3 | DRV8833 driver boards, 5-pack | The muscle controller between brain and motors | [Amazon](https://www.amazon.com/s?k=drv8833+motor+driver+module) | 9 |
| 4 | MAX98357A audio amp | Makes the speaker audible | [adafruit.com/product/3006](https://www.adafruit.com/product/3006) ($5.95) | 6 |
| 5 | 28 mm mini speakers 8 ohm, 2-pack | The mouth | [Amazon](https://www.amazon.com/s?k=28mm+speaker+8+ohm+1w) | 8 |
| 6 | VL53L1X distance sensor | Height sensor (tiny laser aimed at the floor) | [adafruit.com/product/3317](https://www.adafruit.com/product/3317) or [Amazon clones](https://www.amazon.com/s?k=vl53l1x+sensor) | 9 |
| 7 | MPU6050 tilt sensor, 3-pack | Knows when it swings or tilts | [Amazon](https://www.amazon.com/s?k=mpu6050+module) | 8 |
| 8 | PMW3901 optical flow sensor | The speed sensor (how drones hold position) | [Amazon](https://www.amazon.com/s?k=pmw3901+optical+flow+sensor) | 13 |
| 9 | 1S LiPo 300-380 mAh 2-pack + USB 1S charger | The battery (1/40 of a phone battery) | [Amazon](https://www.amazon.com/s?k=3.7v+380mah+lipo+battery+jst) | 14 |

### Box B: the balloon (~$30 + helium)

| # | Item | Why | Where | ~$ |
|---|------|-----|-------|----|
| 10 | 36-inch round foil balloons, 3-pack, silver or white | The body (3 feet across when full) | [Amazon](https://www.amazon.com/s?k=36+inch+round+foil+balloon+silver) | 12 |
| 11 | Modeling clay | Trim weight (pea-sized bits until it floats perfectly) | [Amazon](https://www.amazon.com/s?k=modeling+clay+small+pack) | 5 |
| 12 | Digital scale, 0.1 g precision | Measures trim and helium leak | [Amazon](https://www.amazon.com/s?k=digital+scale+0.1g+precision) | 13 |
| 13 | HELIUM. One phone call: nearest welding-gas store via [airgas.com](https://www.airgas.com) locator or Google "welding gas supply near me". Say exactly: "I need your smallest cylinder of balloon-grade helium, at least 99 percent pure, with a balloon filling valve." Do NOT buy a Balloon Time tank at Walmart or Party City: those are 80 percent helium 20 percent air and will barely lift the electronics | phone call | | 60-115 |

### Box C: the dock (~$45)

| # | Item | Why | Where | ~$ |
|---|------|-----|-------|----|
| 14 | 5 V electromagnet, 25 mm | The dock's hand that grabs the nose | [adafruit.com/product/3872](https://www.adafruit.com/product/3872) ($5.95) | 6 |
| 15 | IRF520 MOSFET modules, 5-pack | The on/off switch for the magnet | [Amazon](https://www.amazon.com/s?k=irf520+mosfet+module) | 7 |
| 16 | Neodymium discs 6x3 mm 50-pack + steel washers | Nose washer + experiments | [Amazon](https://www.amazon.com/s?k=neodymium+magnets+6x3mm) | 8 |
| 17 | Pogo/spring pin contacts | Charging contacts in the cone | [Amazon](https://www.amazon.com/s?k=pogo+pin+spring+connector) | 8 |
| 18 | Foam board 5-pack + hot glue gun | The cone. Ugly is fine | [Amazon](https://www.amazon.com/s?k=foam+board+20x30) | 16 |

### Box D: tools, once, keep forever (~$65)

| # | Item | Where | ~$ |
|---|------|-------|----|
| 19 | Beginner soldering kit (iron, solder, stand, helping hands) | [Amazon](https://www.amazon.com/s?k=soldering+iron+kit+beginner) | 25 |
| 20 | LiPo safety bag | [Amazon](https://www.amazon.com/s?k=lipo+safe+bag) | 8 |
| 21 | 30 AWG silicone wire + JST connector kit | [Amazon](https://www.amazon.com/s?k=30awg+silicone+wire+kit) | 12 |
| 22 | USB-C DATA cables x2, painter's tape, double-sided foam tape, fishing line | [Amazon](https://www.amazon.com/s?k=double+sided+foam+tape) | 15 |
| 23 | Decibel meter, or skip it: the free NIOSH SLM iPhone app is fine | [Amazon](https://www.amazon.com/s?k=decibel+meter) | 0-30 |

At scale this whole aircraft collapses onto one ~$8 custom circuit board,
which is the path to the $30-50 replaceable-unit target (Amendment A1).

---

## Part 2: the build, stage by stage

One stage per sitting. Nothing requires experience.

### Stage 1: unbox day (20 min, no tools)
Lay everything out and identify by sight: the brain (XIAO: thumbnail board
with a tiny camera lens), the muscles (motors: silver AA-battery-end cylinders
with two hair-thin wires), the muscle controllers (DRV8833: stamp-sized
boards), the battery (small silver pillow with a white plug). Plug the XIAO
into your Mac with a USB-C DATA cable. Green light = alive. Photograph the
layout.

### Stage 2: learn to solder on garbage (30 min)
Watch any 10-minute "soldering basics for beginners" video. Then: strip 5 mm
from two wire scraps, twist together, touch the iron to the joint 2 seconds,
feed in a little solder, remove. Shiny teardrop = good, gray blob = reheat.
Five practice joints and you are qualified for this entire build, because the
build only ever needs that exact move.

### Stage 3: make one motor spin (1 hour, the confidence stage)

```
FIGURE 1: the first circuit (one motor)

  Mac USB-C ---> [XIAO brain]
                  pin D0 --------> [DRV8833] IN1        [motor]
                  pin D1 -------->           IN2   OUT1 --o red wire
                  3V3    -------->           VCC   OUT2 --o blue wire
                  GND    -------->           GND
```

Solder wires XIAO D0/D1/3V3/GND to the DRV8833 as drawn; motor wires to
OUT1/OUT2. The firmware is ALREADY in this repo (`firmware/`, built
2026-07-27): run ONE command (`make flash-bench`) and it spins the motor
slow-medium-fast (20/30/50 percent) in a loop, printing the numbers over
serial. Hold the decibel app 1 m away and write down the number at the slow
setting: that is Meemoo's real in-flight voice level, personally measured.

### Stage 4: build the gondola (2 hours)

Everything glues to one credit-card-sized piece of foam board:

```
FIGURE 2: gondola layout, top view (~9 cm x 5 cm)

   [motor UP]                       [motor UP]      UP props: lift/lower
      |    [XIAO camera faces ->]      |
   +--+--------------------------------+--+
   |  [DRV8833][DRV8833][battery]         |
   |  [MPU6050][PMW3901 faces floor]      |
   +--+--------------------------------+--+
   [motor BACK]                     [motor BACK]    BACK props: push/turn

   [VL53L1X points straight down]
   [speaker glued face-down at the front]
```

Wire each part to the XIAO with the same Stage-2 solder move. The exact
pin-by-pin table is in `firmware/README.md` (it is the wiring truth; the
code reads the same table). Foam-tape the boards down. Weigh the finished
gondola: target under 55 grams. Write it down.

### Stage 5: fill and trim the balloon (30 min, the magic one)
1. Fill one 36-inch balloon SLOWLY from the cylinder until round and just
   barely wrinkle-free. Firm pillow, not drum-tight.
2. It pulls up with ~300 g. Tie it to a chair.
3. Foam-tape the gondola under the belly: camera sideways, lasers down.
4. The clay ritual: still rising? add a pea of clay. Sinking fast? pinch some
   off. Done when, released at chest height, it takes ~10 seconds to sink the
   last meter. That slow sink is deliberate: a dead battery means a feather
   landing, never a ceiling stranding.

### Stage 6: first flight in your room
Windows closed, AC off (drafts are the only predator). Fishing-line leash to
a chair. Flash the flight firmware (`make flash-flight`, WiFi name goes in
`firmware/include/meemoo_config.h` first) and open the app's Flight Test page:
Studio > Under the hood > Flight Test bench, or just /flight-test. Four
sliders (up/down, forward/back, turn, power) and a STOP button; today they
fly the simulator whale, over WiFi they drive these same motors. Push up
gently. It rises. You are flying a robot you built. Practice, then drop the
leash.

### Stage 7: the dock cone (2 hours, cardboard first)

```
FIGURE 3: the dock, side view

  wall/table --+
               |  +----------------\
   [magnet]----+ <|    <- cone      \       Meemoo flies in nose-first ->
   [contacts]--+ <|   40 cm mouth    \      cone guides the nose to center,
               |  +----------------/        magnet clicks it home, charging
  webcam on top, looking out along the approach path
```

Foam-board cone, UPDATED per the 3D physics validation (2026-07-28,
docs/PHYSICS_VALIDATION.md): make it SHALLOW - 40 cm mouth, only ~15 cm
deep. The physics rig proved two things about the original deep cone: a
3-foot balloon seats on the rim of a 40 cm mouth with its nose well short
of a deep throat, and a wide throat cannot hand the nose to a small magnet
(it stalls up to 5 cm off-axis). So: put the electromagnet where the nose
NATURALLY rests when the balloon leans into the mouth (test by hand first,
mark the spot), and hot-glue a small paper cup with the bottom cut out
around the magnet as a second-stage centering funnel (cup mouth ~10 cm
narrowing to the magnet face). Wire the magnet through the MOSFET to USB
power. Steel washer on a bottle cap taped to the balloon's nose. Hand-fly
it in nose-first: if the cone + cup guide the nose to the magnet, you have
personally answered the one hardware question nobody on Earth has
published. If it stalls, tell Claude: the plan-B winch (one extra $12
motor) gets designed that night.

### Stage 8: hand it to the software
One session together: point the app's video source at the balloon's camera
instead of the webcam, hand the sliders' job to the software that already
flies the simulator, and Meemoo does its rounds in your actual room. All of
that software exists and is tested; the hardware just plugs in.

## When something goes wrong (normal, expected)

| Symptom | Almost always | Fix |
|---|---|---|
| Motor won't spin | A gray-blob solder joint | Reheat 2 s, touch of solder |
| Board invisible to Mac | Charge-only USB cable | Use the data cable |
| Balloon droops overnight | Normal helium seep (~0.5 g/day) | Pinch off clay; refill weekly-ish |
| Balloon drifts on its own | A draft you can't feel | AC off, doors closed |
| Nose won't center in cone | The plan-B scenario | Claude designs the winch |
