# Helpee — Bench Experiment Order List (Phase 9)

> Created 2026-07-25. Everything needed for the noise test, leak test, and the
> funnel-vs-winch capture test — before any custom envelope or PCB exists.
> Prices are July-2026 estimates; buy the cheap version of everything.

## A. Lift + envelope (~$50 without helium, helium separate)

| Item | Qty | Est. $ | Where / notes |
|---|---|---|---|
| 36" (91 cm) round mylar balloons | 3 | $15 | Amazon/party store. One flies, one leaks (test), one spare. Round = matches the sphere form target |
| **Balloon-grade helium ≥99%** | 1 cyl | $60–115 | ⚠️ **NOT a party-store Balloon Time tank** — those are now 80/20 helium/air (20% lift loss, unusable for trim tests). Airgas/welding-gas supplier, smallest balloon-grade cylinder + regulator, or a party store that fills from a pure cylinder (ask). |
| Modeling clay | 1 pack | $5 | Ballast for neutral trim |
| Digital scale, 0.1 g resolution | 1 | $15 | Amazon. Leak-rate + trim measurement |
| $30 SPL meter (or NIOSH app + calibration check) | 1 | $30 | Noise validation @ 1 m |

## B. Flight electronics (~$60)

| Item | Qty | Est. $ | Notes |
|---|---|---|---|
| Seeed XIAO ESP32S3 Sense (camera + mic onboard) | 2 | $28 | One for bench, one spare. This is the future aircraft brain |
| Coreless motors 6×14 mm (~53k RPM) | 6 | $9 | DFRobot/Amazon; 4 + 2 spares |
| 45 mm props (Gemfan or similar, multipack) | 1 pack | $5 | Bigger/slower = quieter; get 3-blade if available |
| DRV8833 dual H-bridge breakout | 2 | $6 | |
| 1S LiPo 300 mAh + USB 1S charger | 2+1 | $12 | Charge supervised only, bag it |
| MAX98357A I2S amp breakout | 1 | $5 | |
| 28 mm mylar speaker 8 Ω 1 W | 2 | $4 | Speech intelligibility test |
| VL53L1X ToF breakout | 1 | $8 | Altitude hold later |
| MPU6050 IMU breakout | 1 | $4 | Swing damping later |

## C. Dock capture rig (~$45)

| Item | Qty | Est. $ | Notes |
|---|---|---|---|
| 5 V electromagnet, P20/15 class (2.5 kg hold) | 2 | $10 | Adafruit 3872 or equiv |
| Logic-level MOSFET driver module | 2 | $4 | Magnet on/off + reverse-pulse experiment |
| N42 disc magnets 6×3 mm + steel washers | 1 pack | $8 | Capture disc on the balloon nose |
| Spring/pogo contact pins + brass strip | 1 set | $8 | Ring-contact mockup |
| USB webcam (1080p, wide FOV) | 1 | $25 | Dock guidance camera; also the perception dev camera |
| IR LEDs (850 nm) + photodiodes | 1 kit | $8 | Terminal homing experiment (optional this round) |
| Foam board + hot glue | — | $10 | The cone. Cardboard works too |
| 5 V 3 A USB PSU | 1 | $8 | Powers dock rig |

## D. Base station (Brady said he'll dedicate hardware)

| Option | $ | Verdict from research |
|---|---|---|
| **Mac mini M4 24 GB** | ~$999 | Recommended: only tier that runs the full local loop <1 s, silent, unified memory |
| Jetson Orin Nano Super 8 GB | ~$250–400 | The alternative if he wants Chatterbox-Turbo-grade voice 100% local; CUDA maintenance + fan |
| (defer) develop on MacBook | $0 | Fine for all of Phases 0–8 |

**Bench total ≈ $200–215 + helium ($60–115) + optional base station.**

## Order of experiments once parts arrive
1. Noise (1 hour): motor+prop at 20–30% throttle, SPL @ 1 m.
2. Leak (passive, 2 weeks): balloon lift vs day on the scale.
3. **Capture (20 min, the big one):** neutral-ballasted balloon, hand-push
   nose-first into the cone — centers or stalls? → funnel vs winch decision.
4. Magnet hold overnight through HVAC cycle; release + residual-force check.
5. Dock-cam tracking of balloon-on-string: 20 Hz, ~1 cm, 3 lighting setups.
