# Research 05 — Camera-Based Fall Detection (July 2026)

> Produced 2026-07-25 by the fall-detection research agent. Part of the Helpee
> pre-build research phase. See docs/RESEARCH.md for the synthesis.

**Headline finding that should change the spec:** the initial heuristic is right in substance but wrong in logic. It reads as `horizontal-near-floor AND stayed-15s`. Make it **state-persistence primary, descent-transition corroborating** — never a required conjunct. Evidence: Kepler Vision's Night Nurse samples **one image every five seconds** (0.2 fps) and still reports detecting *every* fall over a nine-month evaluation with one false alarm per sensor per 92 days ([keplervision.eu](https://keplervision.eu/en/night-nurse/), [false-alarm claim](https://keplervision.eu/en/one-false-alarm-every-three-months-thanks-to-ai/), [MOBOTIX](https://www.mobotix.com/en/nurseassist-extended)). At 0.2 fps you cannot measure descent velocity at all. Their recall comes entirely from *recognising the fallen state and its persistence*. Descent velocity is a **precision** tool (it separates fall from intentional lie-down); persistence is the **recall** engine. If you AND them, every occluded, off-frame, or low-fps-missed descent becomes a missed fall — the catastrophic failure mode.

Supporting datapoint: in SafelyYou's 436-fall memory-care study, **fallers could not stand up alone in 97.6% (247/253) of cases** ([JMIR / PMC8277400](https://pmc.ncbi.nlm.nih.gov/articles/PMC8277400/)). A consequential fall is almost definitionally persistent. Persistence is a near-free high-recall signal.

---

## A. Recommended V1 Algorithm

### A.1 Signals (all from MediaPipe Pose 33 landmarks, all scale-normalised)

Everything must be normalised by a body-scale term, because pixel distances vary with depth. Use **torso length** as the scale unit:

```
mid_hip      = (landmark[23] + landmark[24]) / 2
mid_shoulder = (landmark[11] + landmark[12]) / 2
S            = running_median(||mid_shoulder - mid_hip||)   # "torso-length", the unit
```

Torso length is the right choice because it stays visible when legs are occluded by furniture — the dominant occlusion case.

| Signal | Definition | Notes |
|---|---|---|
| `torso_angle` | angle between `(mid_shoulder - mid_hip)` and image vertical | primary posture signal |
| `support_y` | max image-y over visible hip/shoulder/knee landmarks | the body's lowest point; "how low am I" |
| `elevation` | `(floor_y(x) - support_y) / S` | **height above the calibrated floor line, in torso-lengths** — the couch/bed discriminator |
| `v_descent` | `Δ(mid_hip_y) / Δt / S` | torso-lengths per second |
| `motion_energy` | mean over landmarks of `‖Δp‖ / (S·Δt)` , median-filtered | breathing/settling ≈ <0.02; purposeful ≳0.1 |
| `vis_frac` | fraction of landmarks with visibility > 0.5 | occlusion / partial-frame detector |
| `aspect` | pose bbox height/width | cheap corroborator, works when pose is degraded |

### A.2 Floor and furniture calibration (this is the whole ballgame)

Nobi runs a **~2-week per-room learning phase** during which "the lamp familiarises itself with its environment, learning to distinguish when someone is lying on a bed, sitting at a table, or has experienced a fall," and **triggers no alarms during that phase** ([Nobi FAQ](https://irp.cdn-website.com/1967ce78/files/uploaded/Nobi_Smart_Lights_FAQ.pdf)). A deployed product with a claimed 100% detection rate considers per-room geometry learning mandatory. Copy this.

Implementation, no depth sensor needed:

1. **Floor line.** Collect frames where the person is confidently UPRIGHT (`torso_angle < 25°`). Record ankle-midpoint `(x, y_ankle)` and pixel body height. Fit `floor_y(x) = a·x + b` (a planar floor under modest camera roll projects to a line). Also fit `S(y_ankle)`, giving a per-depth scale prior — useful on its own for rejecting bad pose scale.
2. **Elevated-support zones.** Whenever a stable SITTING or LYING pose is observed with `elevation > 0.35`, accumulate `(x, support_y)` into a 2-D occupancy grid. Over days this grid *is* the bed/couch/armchair map, learned from actual use rather than declared.
3. **Day-one bootstrap.** Run YOLOv8n (COCO) once at install — `bed`, `couch`, `chair`, `dining table` are all COCO classes — to seed the zone grid so day-one behaviour isn't naive. Weight learned evidence above the detector over time.
4. **Guided placement check.** At install, require that the floor be visible in the lower third of frame and the main seating be in view. Refuse to arm otherwise.

This directly implements the mitigation the literature converges on: "Fall confirmation required floor information in order to distinguish between a human lying on the sofa and a human falling" ([Fall Detection System-Based Posture-Recognition, PMC8321307](https://pmc.ncbi.nlm.nih.gov/articles/PMC8321307/)); scene-segmentation into dangerous floor regions vs. safe furniture regions; and homographic ground-plane projection from [IEEE 7400562](https://ieeexplore.ieee.org/document/7400562).

### A.3 Thresholds

Grounded from [PMC8321307](https://pmc.ncbi.nlm.nih.gov/articles/PMC8321307/) (97.29% accuracy, 97.48% sensitivity, 2.94% FP on 159 falls / 136 ADLs) and the well-trodden open-source heuristics:

```python
# posture
HORIZONTAL_ANGLE      = 55.0   # deg from vertical; >55 => horizontal-ish
NEAR_FLOOR_ELEVATION  = 0.35   # torso-lengths above floor line; <0.35 => on the floor
FURNITURE_ELEVATION   = 0.35   # >=0.35 => supported by something

# descent (precision signal, NOT required)
BALLISTIC_V           = 1.2    # torso-lengths/sec peak, sustained >=0.15 s
BALLISTIC_DROP        = 1.5    # torso-lengths of hip drop within 0.8 s
CONTROLLED_MAX_V      = 0.6    # intentional lie-down stays under this

# stillness
STILL_MOTION          = 0.02   # torso-lengths/sec, median-filtered
PURPOSEFUL_MOTION     = 0.10

# timers (seconds)
T_SETTLE              = 1.5
T_CANDIDATE           = 5.0    # dispatch blimp HERE, not at 15
T_CONFIRM             = 15.0   # spec's person.down
T_VOICE_1             = 8.0
T_VOICE_2             = 18.0
T_ESCALATE            = 50.0
T_LONGLIE             = 90.0   # backstop path, descent never observed
T_RECOVERED           = 2.0    # upright + normal height held this long
```

The transition-speed discriminator has direct empirical backing: falls complete in **under ~25 frames (~1 s)** while intentional lying-down takes **more than ~80 frames (~3.2 s)** ([PMC8321307](https://pmc.ncbi.nlm.nih.gov/articles/PMC8321307/)). That paper also gates on ≥85% of the silhouette intersecting the floor region — the `elevation` term is the pose-based equivalent.

### A.4 State machine

```
                    ┌──────────┐
                    │ UPRIGHT  │◄──────────────────────┐
                    └────┬─────┘                       │
       horizontal or low │                             │ upright & normal height
                         ▼                    ┌────────┴────────┐
                  ┌──────────────┐            │    RECOVERED    │
                  │  DESCENDING  │            │ (log near-miss) │
                  └──────┬───────┘            └────────▲────────┘
                 settled │ (T_SETTLE)                  │
                         ▼                             │
              ┌──────────────────────┐                 │
              │  GROUNDED_CANDIDATE  │─────────────────┤
              └──────┬───────────────┘                 │
        T_CANDIDATE  │  → emit candidate.fall          │
        + dispatch   │     (INTERNAL only, no alarm)   │
           blimp     ▼                                 │
              ┌──────────────────┐                     │
              │   CONFIRMED_DOWN │  T_CONFIRM=15s      │
              │  → person.down   │  → emit event       │
              └──────┬───────────┘                     │
                     ▼                                 │
              ┌──────────────────┐   "I'm fine"        │
              │    VERIFYING     │─────────────────────┤
              │ voice ×2 + motion│                     │
              └──────┬───────────┘                     │
      no response    │                                 │
      or "help"      ▼                                 │
              ┌──────────────┐                         │
              │   ESCALATE   │                         │
              └──────────────┘                         │

  ── independent parallel path, no descent required ──
  LONG_LIE:  horizontal/low + not-a-rest-zone + motion<STILL
             for T_LONGLIE (90 s)  →  GROUNDED_CANDIDATE
  ── independent parallel path, blimp/frame-edge ──
  VANISHED_DOWN: pose exits bottom of frame with v_descent
                 > BALLISTIC_V  →  GROUNDED_CANDIDATE
```

### A.5 Couch/bed suppression logic (precise)

```python
def classify_grounded(st):
    on_furniture = (st.elevation >= FURNITURE_ELEVATION
                    and st.zone_grid.is_rest_zone(st.x, st.support_y))

    ballistic = (st.v_peak > BALLISTIC_V
                 or st.hip_drop_0_8s > BALLISTIC_DROP)

    # A ballistic descent ALWAYS overrides furniture suppression.
    # Falls out of bed and off chairs are real and common.
    if ballistic:
        return "CANDIDATE"

    if on_furniture:
        # still tracked, not alarmed — but three escapes remain
        if st.slid_toward_floor():                 return "CANDIDATE"
        if st.habitual_rest_time is False and \
           st.motion_energy < STILL_MOTION and \
           st.duration > 30 * 60:                  return "CANDIDATE"
        return "SUPPRESSED_FURNITURE"

    if st.elevation < NEAR_FLOOR_ELEVATION:
        # on the floor, controlled descent: yoga / prayer / reaching / napping.
        # Recall-over-precision: do NOT hard-suppress. Ask.
        # Use a longer timer and a gentler opening line.
        return "CANDIDATE_SOFT"

    return "MONITOR"
```

`CANDIDATE_SOFT` is the key concession to the recall-over-precision tuning. A deliberate floor-sitter gets asked a friendly question after ~40 s rather than 15 s, and never gets escalated if they answer. The cost of the wrong guess is one question; the cost of hard-suppressing is a missed fall.

### A.6 Two engineering decisions worth making now

- **Ring-buffer skeletons, not video.** Keep a rolling 60 s buffer of landmark sequences (JSONL, ~50 KB/min) for every candidate event. This is privacy-preserving, it is how to build an eval set from real deployments, and it is the single highest-leverage lever on long-run accuracy. Both AltumView (stick-figure-only product view) and Nobi (optional abstract-figure rendering, "images are not saved") ship this idea.
- **Ship a learning phase.** Arm detection at reduced sensitivity for the first 7–14 days while the floor line and zone grid populate, and tell the user that's what's happening. Nobi does exactly this and suppresses alarms entirely during it.

---

## B. Test Clip Plan for pytest

### B.1 Licensing verdict

Authoritative licence table, cross-checked against the OmniFall paper's own audit ([arXiv 2505.19889](https://arxiv.org/html/2505.19889v3)):

| Dataset | Licence | Bundle in a private/commercial repo? |
|---|---|---|
| **GMDCSA-24** | MIT (repo) / CC BY (article) | ✅ **Yes.** Both permissive. |
| **CaucaFall** | CC BY 4.0 | ✅ **Yes.** Attribution only. |
| Le2i / IMVIA | CC BY-**NC**-SA 3.0 | ⚠️ Non-commercial + share-alike. Dev-only, keep out of the repo. Original host dead; Kaggle mirror exists. |
| UR Fall | CC BY-**NC**-SA 4.0 | ⚠️ Same verdict. |
| OmniFall annotations | CC BY-**NC**-SA 4.0 | ⚠️ Labels only — no videos shipped. |
| OF-Synthetic (12k clips) | via HF, NC terms | ⚠️ Dev-only, but **the only eye-level source** (see B.3). |
| OF-In-the-Wild (OOPS) | CC BY-NC-SA 4.0 | ⚠️ Dev-only. |
| NTU RGB+D | Research-only, registration + release agreement, **explicit no-redistribution** | ❌ **No.** |
| MCFD (Montreal), CMDFall, UP-Fall, EDF, OCCU | Author permission required | ❌ **No.** |

**Verdict: bundle GMDCSA-24 + CaucaFall. Nothing else.**

### B.2 Why GMDCSA-24 is almost purpose-built for V1

From the Data-in-Brief paper ([PMC11416611](https://pmc.ncbi.nlm.nih.gov/articles/PMC11416611/)) and the [GitHub repo](https://github.com/ekramalam/GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos):

- 81 fall + 79 ADL clips, 4 subjects, 3 real home setups, 720p/640×480, 30 fps, H264, shot on a **0.92 MP integrated webcam**.
- **Camera heights: 64 cm, 70 cm, 90 cm, and 135 cm.** That is a laptop-on-a-desk and a shelf. The V1 sensor geometry, almost exactly — not a CCTV corner mount.
- Recorded **day (light on/off) and night (low light)**, with clothing variation.

CaucaFall adds what GMDCSA lacks: 10 subjects, 5 fall types + 5 ADLs, deliberate occlusions, natural/artificial/night lighting, varied floor textures, varied fall angles and camera distances, plus **per-frame segmentation labels** ([Mendeley](https://data.mendeley.com/datasets/7w7fccy7ky/4), [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2352340922008162)).

### B.3 Eye-level clips — the honest answer

**No published real-video dataset is shot at blimp eye level.** The closest things:

- GMDCSA-24's 135 cm camera (chest height on a standing adult, eye level on a seated one).
- **OF-Synthetic** is the only source with a systematic eye-level axis: it varies elevation across "eye-level, low, high/CCTV perspective, top-down/birds eye" × azimuth × distance, 12,000 clips / 17 h, auto-downloadable from [hf.co/datasets/simplexsigil2/omnifall](https://huggingface.co/datasets/simplexsigil2/omnifall) (~9.1 GB). Non-commercial, so dev/eval only — but it is exactly the right probe for "does our geometry survive eye level."

For the blimp camera **shoot your own**, and 20–30 clips is enough for a regression suite. That is not a gap in the research; it is genuinely novel viewpoint.

### B.4 Repo structure — commit landmarks, not video

```
tests/
  fixtures/
    landmarks/            # ✅ COMMITTED — JSONL landmark sequences, ~50KB each
      gmdcsa/  s1_fall_01.jsonl ...
      caucafall/ ...
      helpee_eyelevel/    # our own recordings
    clips/                # ⬇️  fetched by script, gitignored, ~0.5GB
      fetch.py            # downloads GMDCSA + CaucaFall from source, checks hashes
    labels/
      *.json              # OmniFall 16-class taxonomy per clip
  test_fall_statemachine.py
  test_furniture_suppression.py
  test_recovery.py
  golden_thresholds.json  # thresholds as a committed file; tuning shows up as a diff
```

Committing extracted **landmark sequences** rather than video makes CI fast and hermetic (no video decode, no MediaPipe in CI), keeps the repo small, and sidesteps any residual redistribution worry entirely — landmark coordinates are derived data, not the clips. Keep a handful of raw clips locally for genuine end-to-end tests.

Adopt **OmniFall's 16-class taxonomy** for labels ([LABELS.md](https://huggingface.co/datasets/simplexsigil2/omnifall/blob/main/LABELS.md)) — it already encodes the distinction the product lives or dies on:

- `1|fall` — "the act of falling (from any previous state)" vs `5|lie_down` — "lying down **intentionally** (in contrast to a fall)"
- `2|fallen` — "being on the ground or a mattress **after a fall**" vs `6|lying` — "being in a lying position after **intentionally** getting into that position"

### B.5 Mapping to the three spec scenarios

| Scenario | Assertion | Clips |
|---|---|---|
| **1. Genuine fall → `person.down`** | `candidate.fall` within 6 s, `person.down` at 15±1 s, escalation on no voice | GMDCSA-24 all 81 fall clips; CaucaFall's 5 fall types; **including the night/low-light subset** |
| **2. Intentional lying → no alarm** | no `person.down`; at most one `CANDIDATE_SOFT` | GMDCSA-24 + CaucaFall ADL clips containing lie-down/sit; hand-shot yoga/prayer/floor-nap and couch/bed clips |
| **3. Fall then self-recovery** | `candidate.fall` fires, then `RECOVERED` before escalation; near-miss logged | GMDCSA fall clips where the actor stands back up — note OmniFall's warning that staged actors "stand up immediately," which makes these plentiful here and rare in reality |

**Metrics to assert, not just pass/fail:** per-event recall at the *candidate* stage (target 100% on bundled fall clips — a miss here is the catastrophic class), false-candidate rate per ADL-minute, and time-to-candidate distribution.

---

## C. Hard-Case Table

| Case | Failure mode | Mitigation |
|---|---|---|
| **Intentional lying: couch/bed** | Horizontal + still + 15 s → false `person.down` | Learned elevated-support zone grid + `elevation ≥ 0.35` suppression (§A.2/A.5). Nobi's 2-week learning phase does precisely this. |
| **Intentional lying: yoga, prayer, floor nap** | On the *floor*, so elevation gate doesn't save you | `CANDIDATE_SOFT`: longer timer, gentle question, never escalates on an answer. Learn habitual floor-rest zones + times of day. Voice verification is what makes accepting these false candidates cheap. |
| **Fall ending seated/kneeling against furniture — not horizontal** | `torso_angle` stays < 55° → never enters DESCENDING | Do **not** require horizontality. Trigger on *low hip elevation regardless of torso angle*, plus prolonged stillness. AltumView explicitly calls out "sitting on the floor after the falls" as a case their VLM upgrade had to fix ([AltumView, May 2025](https://www.altumview.ca/2025/05/12/altumview-launched-phase-2-of-its-fall-detection-upgrade-powered-by-large-vision-language-ai-model-vlm/)). |
| **Partial occlusion by furniture** | Legs/hips hidden → `vis_frac` collapses, keypoints wrong | Scale on torso length (survives leg occlusion). Add a person-detector bbox channel — confidence-fused YOLO bbox + MediaPipe keypoints is the documented fix ([ACM 3718441.3718446](https://dl.acm.org/doi/10.1145/3718441.3718446)). Occlusion-augmented training yields **+36% (non-deep) / +55% (deep)** accuracy under occlusion ([arXiv 2208.07291](https://arxiv.org/pdf/2208.07291)). Treat low `vis_frac` + last-known-low-position as *evidence for*, never against. |
| **Camera can't see the floor (blimp at eye level)** | Person's floor position is below frame | `VANISHED_DOWN` path (§A.4). Pitch the blimp camera down when dispatched; ≥120° vertical FOV puts floor in frame from ~0.9 m at 1.5 m height. Fundamentally: **don't make the blimp the detector** (§D). |
| **Low light / night** | 64.6% of SafelyYou's bedroom falls were 8 PM–8 AM — the *majority* case | 850 nm IR illuminator + IR-cut-switching camera. Prefer over thermal: BlazePose is RGB-trained, and IR-illuminated grayscale degrades it far less than thermal. **Validate on GMDCSA-24's night clips — labelled low-light data exists.** Night fallback: if pose confidence collapses, drop to silhouette + persistence (the Kepler-style state path), which needs no keypoints. Thermal is the fallback-fallback: 5–15% better than depth/wearable in low light and occlusion ([arXiv 2509.16479](https://arxiv.org/pdf/2509.16479)). |
| **Multiple people (facility mode)** | MediaPipe Pose Landmarker defaults to `num_poses = 1` — a second person can steal the track | Set `num_poses > 1` ([docs](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker)), or better, YOLO person detector → per-crop pose. Then copy **Nobi's Auto-Snooze**: when a second person enters the room, fall detection is deliberately suspended — a witnessed fall gets human help faster than an alert would ([Nobi](https://portal.nobi.life/en/blog/news-6/nobi-s-latest-feature-auto-snooze-69)). Downgrade rather than suppress. |
| **Pets** | Cat/dog triggers motion-based systems constantly | **Largely a non-issue for pose-based pipelines** — BlazePose is a human-pose model and won't produce a confident human skeleton for a quadruped. A real advantage of pose over background-subtraction and radar. |
| **Fall out of bed / off a chair** | Furniture suppression eats a genuine fall | The ballistic override in §A.5 — velocity **always** beats zone suppression. Do not invert this. |
| **Walker / cane / atypical gait** | Non-canonical poses; calibration learns a wrong "upright" | Documented accuracy loss for "people who move differently because of a disability or a walker." Widen `HORIZONTAL_ANGLE` tolerance, and calibrate the upright-posture prior *per person* during the learning phase rather than using a population default. |
| **Rotated / novel viewpoints** | Models trained on canonical views "fail when subjects are viewed from new perspectives" | Viewpoint-augmented training + inference-time aggregation ([PMC12609388](https://pmc.ncbi.nlm.nih.gov/articles/PMC12609388/)). For a geometric heuristic, the floor-line calibration is what makes it viewpoint-portable. |
| **Background furniture biasing a trained classifier** | CNN latches onto beds/chairs → false positives | If a classifier is ever trained: Gaussian-blur the background and apply object-specific contextual transforms during training ([arXiv 2404.08088](https://arxiv.org/html/2404.08088v1)). Another argument for geometry-first in V1. |

---

## D. Stationary vs. Blimp Camera — Verdict

**Base station is the primary detector, mounted high. The blimp is the mobile verifier and the interaction surface. It should not run primary fall detection in V1, and probably not ever.** The evidence is one-directional.

**1. Every deployed product mounts high, and says why.** Nobi is a ceiling pendant lamp (10 m × 10 m coverage; the smaller Nobita ceiling unit covers 5 m × 5 m). Teton renders its training data "from the viewpoint of a number of different **ceiling mounted** cameras… simulating the exact parameters of the sensor we use in production" ([Encord case study](https://encord.com/customers/human-pose-estimation-with-tetonai/)). Kepler uses high 360° optical sensors. Vayyar's radar mounts wall or ceiling. The stated rationale: "if placed centrally on the ceiling, a camera can detect people behind objects," and ceiling placement "helps provide a similar view of every fall and removes furniture that may be between the subject and camera." Occlusion by furniture is *the* dominant failure mode, and elevation is the cheapest fix. An eye-level camera maximises furniture occlusion and can lose the floor entirely.

**2. Aerial/eye-level moving views actively degrade pose estimation.** "Aerial viewpoints tend to occlude pose keypoints of the face or legs, distort body proportions and challenge pose models trained on ground-level images" ([FlyPose, arXiv 2601.05747](https://arxiv.org/pdf/2601.05747)); drone video suffers "variety of camera viewpoints and changing backgrounds caused by drone motion." Ego-motion compensation is required to "isolate the true dynamics of the object of interest," normally done by fusing vision with IMU or GNSS ([arXiv 2603.03904](https://arxiv.org/pdf/2603.03904)). On a slowly drifting blimp, every motion signal — `v_descent`, `motion_energy` — is contaminated by camera motion, and the floor-line calibration is invalid by construction because the camera pose changes continuously.

**3. The exact architecture proposed here is published and works.** [arXiv 2507.10474](https://arxiv.org/html/2507.10474v1) is a three-stage system: cheap always-on detector → localisation → **a robot navigates to the location and streams camera video for vision confirmation, specifically to "distinguish fallen individuals from those sleeping or resting."** Stage-3 vision confirmation scores **96.3%** accuracy; navigation succeeds 95% of the time; if the visit disconfirms, the robot returns to base and the event is logged as a false positive for retraining. That last detail is worth stealing verbatim — verification outcomes are labelled training data, for free.

**Recommended split:**

| | Base station (high-mounted, mains) | Blimp (eye level, mobile) |
|---|---|---|
| Continuous pose + state machine | ✅ primary | ❌ never |
| Floor/furniture calibration | ✅ owns it | ❌ (no stable frame) |
| Long-lie backstop | ✅ | ❌ |
| Dispatch on `candidate.fall` | ✅ triggers | ✅ flies |
| Close-up visual confirmation | — | ✅ single-frame checks, pitched down |
| "Are you okay?" conversation | (fallback speaker) | ✅ **primary value** |
| Escalation decision | ✅ owns it | feeds evidence |

Two caveats stated plainly. First, this makes the base station a hard dependency for the safety feature — fall detection is only as good as camera coverage, and a one-camera install covers one room. SafelyYou found **80.3% of falls occur in bedrooms/bathrooms**, so a living-room-only install misses most falls. Second, the blimp still earns its keep: it converts a *detection* into a *conversation*, and that conversation is what lets recall be tuned aggressively without drowning the user in alarms. A real product advantage, not a consolation prize.

**Where the blimp could later become a detector:** with reliable ego-motion (IMU fused with visual odometry) and a viewpoint-invariant skeleton model, eye-level inference becomes tractable. Measurable gate: blimp-cam pose keypoint error within 1.5× of base-cam error on the same simultaneous fall, and `v_descent` estimates agreeing within 25% after compensation. Until both hold, blimp detection will underperform the base station.

---

## E. What Commercial Products Actually Achieve

### Published numbers

| Product | Sensor / placement | Published performance |
|---|---|---|
| **Kepler Vision Night Nurse** | 360° optical, high mount; on-prem "Edge Box"; **1 image / 5 s** | Detected **every fall with 100% reliability** over a 9-month Dutch care-home evaluation (Jun 2020–Mar 2021). **1 false alarm per sensor per 92 days.** **>99% false-alarm reduction** vs. motion sensors (2,195 alarms in 3 weeks → 9). Caregiver in-room within 5 min in 5 of 6 falls. 14,500 clients, 26 countries. |
| **Nobi smart lamp** | Ceiling pendant, all processing in-lamp | Claims **100% fall detection**, AI trained 6 years on **195,000+ real-life scenarios**. Up to **84% reduction** in care-home falls. ~2-week per-room learning phase. Asks the person if they've fallen; escalates on "yes" **or no response**. |
| **SafelyYou** | Wall/high camera in bedroom + **human review** | 436 falls, 66 residents, 6 facilities, 10 months. Time-on-ground **43.2 → 13.6 min**; time-to-assistance **35.3 → 7.0 min**; on-ground >1 hr **31% → 0%**. Separately: **41% fewer falls, 75% fewer EMT visits, 80% fewer ED visits.** Notably **does not publish sensitivity/specificity.** |
| **Teton.ai** | Ceiling-mounted sensor, IR at night, local processing, signals-not-video | **83% reduction in patient falls in the first 87 days** at a hospital partner. $20M raise, 10 US states by end-2025. |
| **AltumView Sentinare** | Wall sensor, stick-figure-only output | First **VLM-based** fall detection (Apr 2025; Phase 2 May 2025). Claims near-elimination of false alarms *and* missed detections, explicitly including vertical falls, **furniture-occluded falls, and sitting-on-the-floor-after-a-fall**. |
| **Vayyar Care** (radar baseline) | 4D imaging radar, wall or ceiling, 16 m²/unit | Radar literature: **sensitivity >97%, specificity >90%**. Works in total darkness and steam. No pose, no image. |

### Read these numbers sceptically — the calibration

Two of the three "100%" claims are vendor-stated on staged or self-selected evaluations, and SafelyYou — the one with peer-reviewed publications and a **human reviewing every video** — conspicuously reports *outcomes* rather than *detection accuracy*. That omission is informative.

The honest calibration comes from OmniFall ([arXiv 2505.19889](https://arxiv.org/html/2505.19889v3)):

- Models trained on staged datasets score near-perfect in-domain and **collapse in the wild**: Le2i **100 → 58.8** Fall F1; UP-Fall **72.9 → 16.9**. Per-dataset transfer to real footage: CaucaFall 13.8, OCCU 14.5, UP-Fall 16.9, EDF 24.8, GMDCSA 47.0, CMDFall 52.3, Le2i 58.8 Fall F1.
- Training on *all* staged data combined still only reaches **61.2% Fall F1** in the wild (vs. 77.6% in-domain).
- **The `fallen` state is dramatically harder than the `fall` event**: best F1 41.0 (staged+synthetic) rising to 53.6 with in-domain data. Per-source `fallen` F1 bottoms out at 2.7–3.2.
- Zero-shot 8B VLMs (Qwen3-VL-8B: 67.8 Fall F1; InternVL3.5-8B: 68.0) **beat fine-tuned VideoMAE on the fall event** — but **misclassify 95–97% of `fallen` instances as `lying`** on some datasets.
- The paper's own framing: staged datasets show "healthy actors performing falls in controlled settings with safety equipment, so their generalization to real-world deployment remains unknown," and staging bias is worst for the clinically critical fallen state because "actors there stand up immediately."

**So: any "99.15% on UR Fall" figure (three-stream ST-GCN, [Nature Sci Rep](https://www.nature.com/articles/s41598-025-95508-7)) or "98.64% with BlazePose + improved ST-GCN" ([Springer](https://link.springer.com/article/10.1007/s11554-023-01377-6)) is an in-domain staged number and predicts roughly nothing about a real living room.**

**Realistic V1 expectation to state publicly:**
- Recall on *consequential* falls (person cannot self-recover, remains down) — genuinely high, **plausibly 90%+**, because that's the persistence signal and Kepler demonstrates it works even at 0.2 fps. Conditional on the room being in frame.
- Recall on *all* falls including near-falls and self-recovered ones — much lower, **60–80%**, and honestly the near-falls aren't needed.
- False alarms before furniture calibration matures — **several per day**. After the learning phase plus voice verification — target the Kepler band of **~1 escalation per room per month**, but do not claim it until measured in a real home.
- The `fallen`-vs-`lying` confusion is the industry's open problem, not a gap in this implementation. AltumView needed a VLM to move the needle on it. The floor-line geometry is a legitimately good attack on it precisely *because* it's geometric rather than learned — it measures height above the floor rather than asking a model to infer intent from appearance.

---

## F. CPU Budget Plan

### F.1 Measured pose latencies

From the official BlazePose GHUM model card ([Google](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20BlazePose%20GHUM%203D.pdf)):

| Variant | Pixel 4 CPU | Pixel 4 GPU | Desktop | In-browser |
|---|---|---|---|---|
| Lite | 25 ms | 8 ms | 7 ms | 13 ms |
| **Full** | **40 ms** | 9 ms | 8 ms | 15 ms |
| Heavy | 147 ms | 22 ms | 10 ms | 29 ms |

Detector input 224×224×3, landmarker 256×256×3, all float16. An Intel N100 leads a Pi 5 by ~20% (Passmark multithread) to 30–45% (Geekbench 6), and both sit between Pixel-4-CPU and desktop.

**Estimates for an N100, single core, 640×480 capture:**

| Variant | Est. per-frame | Ceiling fps (1 core) | Verdict |
|---|---|---|---|
| Lite | 10–15 ms | 65–100 | headroom to spare |
| **Full** | **15–25 ms** | **40–65** | **recommended default** |
| Heavy | 55–90 ms | 11–18 | only if accuracy demands it |

Pi 5 lands roughly 1.3–1.5× slower. MediaPipe is documented as "processing images at 30+ FPS on CPU alone" ([Roboflow](https://blog.roboflow.com/best-pose-estimation-models/)). Smaller fallback: MoveNet Lightning is ~7 ms on *mobile* CPU.

### F.2 Far less fps is needed than intuition suggests

Fall descent lasts ~0.5–1.0 s. At 15 fps that's 8–15 frames — ample to estimate `v_descent`. Below ~8 fps velocity estimation gets noisy. And Kepler runs its always-on tier at **0.2 fps** and gets 100% recall from state persistence. Frame rate buys *precision* (velocity discrimination), not recall.

### F.3 Three-tier duty cycle

```
IDLE      motion gate only, 3 fps, 160x120 grayscale frame-diff / MOG2
          cost: <1 ms/frame  →  ~0.3% of one core
          triggers when foreground pixel fraction crosses a threshold

ACTIVE    person present & moving: MediaPipe Full at 15 fps
          cost: ~25 ms x 15 = 375 ms/s  →  ~38% of one core

TRACKING  candidate fall in progress: 15 fps held, plus voice pipeline
          cost: ~45% of one core, bounded by the verification window (~60 s)
```

Motion gating is well-established. In a real home the person is absent or still most of the day, so expect a **10–30% ACTIVE duty cycle** → **realistic sustained load of 5–15% of one core** on an N100. A rounding error on a 4-core part.

One subtlety: gate on motion, but **do not let the gate be the only path into the state machine.** A person who has fallen and is lying still generates no motion. Once a person has been seen, keep pose running until they are confirmed upright-and-gone or a rest-zone/absence timeout expires. Otherwise the motion gate systematically blinds the system to precisely the state it's hunting.

### F.4 Thermal and power

- **Base station: mains power, no debate.** At 5–15% sustained on a 6 W-TDP-class N100, a fanless mini-PC is thermally comfortable indefinitely. A Pi 5 running sustained pose needs active cooling — factor the fan into the acoustic design of a device in a living room.
- **Blimp: verification bursts only.** Continuous onboard pose is the wrong call on payload, battery, and accuracy grounds simultaneously. Run inference in ≤60 s bursts on dispatch. If the blimp instead streams frames to the base station for the close-up check, onboard compute drops to a radio and the weight budget goes to flight time. Likely the right trade.
- **Model choice under thermal pressure:** drop Full → Lite before dropping fps. Losing keypoint precision hurts `v_descent` (a precision signal); losing fps hurts it more, and losing the persistence path hurts recall.

### F.5 Multi-person cost

`num_poses = N` multiplies landmarker cost roughly linearly (the detector runs once). For facility mode, YOLOv8n-person → per-crop MediaPipe scales better and tracks identities properly. Budget ~25 ms × N on N100 and cap N at 3–4.

---

## Three things to do first

1. **Build the floor-line + zone-grid calibration before tuning any threshold.** Every hard case in section C routes through it, and no threshold tuning compensates for its absence. It is also what makes the couch/bed problem tractable without training a model.
2. **Restructure the trigger as `persistence OR (transition AND persistence)`, never `transition AND persistence`.** Add the `LONG_LIE` and `VANISHED_DOWN` paths. A small code change that removes the entire class of "we never saw the descent" misses — the class that contains the catastrophic failures.
3. **Start the pytest suite from GMDCSA-24's 160 clips today** — MIT/CC BY, webcam-shot at 64–135 cm, day and night. Commit extracted landmark JSONL rather than video. A real regression suite this week, with camera geometry closer to V1 than any CCTV-mount dataset.

### Sources
[arXiv 2505.19889 OmniFall](https://arxiv.org/html/2505.19889v3) · [OmniFall on HF](https://huggingface.co/datasets/simplexsigil2/omnifall) · [OmniFall LABELS.md](https://huggingface.co/datasets/simplexsigil2/omnifall/blob/main/LABELS.md) · [arXiv 2507.10474 robot vision confirmation](https://arxiv.org/html/2507.10474v1) · [PMC8321307 posture thresholds](https://pmc.ncbi.nlm.nih.gov/articles/PMC8321307/) · [PMC8277400 SafelyYou JMIR](https://pmc.ncbi.nlm.nih.gov/articles/PMC8277400/) · [SafelyYou AJMC/PRNewswire](https://www.prnewswire.com/news-releases/new-research-reveals-safelyyous-ai-enabled-fall-detection-reduces-need-for-emergency-service-care-in-dementia-care-facilities-300885778.html) · [Kepler Night Nurse](https://keplervision.eu/en/night-nurse/) · [Kepler false alarms](https://keplervision.eu/en/one-false-alarm-every-three-months-thanks-to-ai/) · [MOBOTIX/Kepler](https://www.mobotix.com/en/nurseassist-extended) · [Nobi FAQ PDF](https://irp.cdn-website.com/1967ce78/files/uploaded/Nobi_Smart_Lights_FAQ.pdf) · [Nobi Auto-Snooze](https://portal.nobi.life/en/blog/news-6/nobi-s-latest-feature-auto-snooze-69) · [Teton/Encord](https://encord.com/customers/human-pose-estimation-with-tetonai/) · [AltumView VLM Phase 2](https://www.altumview.ca/2025/05/12/altumview-launched-phase-2-of-its-fall-detection-upgrade-powered-by-large-vision-language-ai-model-vlm/) · [Vayyar Care](https://vayyar.com/care-pages/how/) · [BlazePose GHUM model card](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20BlazePose%20GHUM%203D.pdf) · [MediaPipe Pose Landmarker docs](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker) · [GMDCSA-24 paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11416611/) · [GMDCSA-24 repo](https://github.com/ekramalam/GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos) · [CaucaFall Mendeley](https://data.mendeley.com/datasets/7w7fccy7ky/4) · [CaucaFall paper](https://www.sciencedirect.com/science/article/pii/S2352340922008162) · [UR Fall](https://fenix.ur.edu.pl/~mkepski/ds/uf.html) · [NTU RGB+D ROSE Lab](https://rose1.ntu.edu.sg/dataset/actionRecognition/) · [MCFD Montreal](http://www-labs.iro.umontreal.ca/~labimage/Dataset/) · [arXiv 2404.08088 visual context](https://arxiv.org/html/2404.08088v1) · [arXiv 2208.07291 occlusion](https://arxiv.org/pdf/2208.07291) · [PMC12609388 occluded/rotated views](https://pmc.ncbi.nlm.nih.gov/articles/PMC12609388/) · [ACM YOLOv5+MediaPipe fusion](https://dl.acm.org/doi/10.1145/3718441.3718446) · [FlyPose arXiv 2601.05747](https://arxiv.org/pdf/2601.05747) · [UAV tracking arXiv 2603.03904](https://arxiv.org/pdf/2603.03904) · [arXiv 2509.16479 thermal](https://arxiv.org/pdf/2509.16479) · [Nature three-stream ST-GCN](https://www.nature.com/articles/s41598-025-95508-7) · [Springer BlazePose+ST-GCN](https://link.springer.com/article/10.1007/s11554-023-01377-6) · [arXiv 2503.19501 CPU pose fall detection](https://arxiv.org/abs/2503.19501) · [Roboflow pose model speeds](https://blog.roboflow.com/best-pose-estimation-models/) · [16dina/fall-detection](https://github.com/16dina/fall-detection) · [zhahoi/yolov8-pose-fall-detection](https://github.com/zhahoi/yolov8-pose-fall-detection) · [rhafaelc/Fall-Detection-YOLO-MediaPipe](https://github.com/rhafaelc/Fall-Detection-YOLO-MediaPipe) · [IEEE 7400562 homography](https://ieeexplore.ieee.org/document/7400562)
