# Research 07 — SAR / HRI Academic Landscape (July 2026)

> Produced 2026-07-25 by the SAR-academic research agent. Part of the Helpee
> pre-build research phase. See docs/RESEARCH.md for the synthesis.

**Lead finding, because it reframes the whole pitch:** the single most useful paper came out of Matarić's own lab in June 2025 and is almost purpose-built to justify Helpee. Kian et al., *Engagement and Disclosures in LLM-Powered CBT Exercises: Robot vs. Chatbot Over Time* (https://arxiv.org/abs/2506.17831) ran 26 participants through two weeks of daily CBT exercises in their own residences, comparing an LLM-powered socially assistive robot against a disembodied chatbot. Significant time × embodiment interaction: **engagement and the intimacy of personal disclosures increased over time in the robot condition and decreased in the chatbot condition.** Same language model. That single result answers "why not a smart speaker," answers "won't the novelty wear off," and came from her students. Leading with it signals the founder read her lab's current work, not just her 2013 greatest hits.

---

## A. Matarić lab map, and what she counts as success

**Position.** Chan Soon-Shiong Chair and Distinguished Professor of CS, Neuroscience, and Pediatrics at USC; founding director of the Robotics and Autonomous Systems Center; elected to the National Academy of Engineering February 2025 (https://viterbischool.usc.edu/news/2025/02/maja-mataric-elected-to-the-nae/). Co-pioneered SAR with Brian Scassellati around 2000. Defines it as enabling "intelligent machines to help people help themselves through personalized, assistive social (rather than physical) interactions" (https://en.wikipedia.org/wiki/Maja_Matari%C4%87). Her framing phrase is **human augmentation rather than automation**. In IEEE Spectrum (https://spectrum.ieee.org/socially-assistive-robotics) she describes the question driving her move into SAR as "How can we help someone live a better life?"

**Current output (2025–2026), from the arXiv record:**

| Paper | Date | Why it matters to Helpee |
|---|---|---|
| *Engagement and Disclosures in LLM-Powered CBT Exercises: Robot vs. Chatbot Over Time* (Kian et al.) | Jun 2025 | The embodiment argument. See above. |
| *Personalized Socially Assistive Robots with End-to-End Speech-Language Models for Well-Being Support* (Fu, Shi, … Matarić) | Jul 2025 | N=11 within-participant; participants valued empathetic feedback, **natural turn-taking, back-channeling**, adaptive responses; stated limitation was nonverbal synchronization. Sets the voice-stack bar. |
| *HRIBench: Benchmarking Vision-Language Models for Real-Time Human Perception* (Shi et al.) | Jun 2025 | Her own group finding current VLMs **struggle** with real-time human perception. Do not overclaim fall detection. |
| *The Illusion of Intervention: Your LLM-Simulated Experiment is an Observational Study* (Lin, Yun, Matarić, Canny, Gretton, D'Amour) | May 2026 | She is actively arguing LLM-simulated user studies are confounded. **Do not bring simulated-user results as evidence.** |
| *Multi-Week, In-Class Deployments of Telepresence Robots With Four Homebound K-12 Students* (Rueben et al.) | May 2026 | Multi-week, N=4, real deployment. Small-N longitudinal in-the-wild is her house style. |
| *Improving through Interaction: CMA-ES-IG* (Dennler et al.) | Mar 2026 | Preference learning that optimizes the user's experience of being asked. |
| *Exploring Socially Assistive Peer Mediation Robots for Teaching Conflict Resolution* (Shrestha et al.) | Mar 2026 | Robot as scaffold for human-to-human skill. |
| *Modeling Personalized Difficulty of Rehabilitation Exercises Using Causal Trees* (Dennler et al.) | May 2025 | Stroke survivors; interpretable per-person models. |
| *Conversational Planning for Personal Plans* (Christakopoulou et al.) | Feb 2025 | LLM as meta-controller for long-horizon coaching. |
| *Sleepless Nights, Sugary Days: Synthetic Users With Health Conditions* | Feb 2025 | Synthetic-user harness for evaluating coaching agents. |
| *Toward Anxiety-Reducing Pocket Robots* / *Inducing Calmness With Pocket-Sized Robotics* (Frederiksen, Støy, Matarić) | Mar 2025 / May 2026 | Tactile, minimal-form, physiological outcomes. |

**Funded trials.** An NIH-funded RCT of SAR for student anxiety at USC, and a 2024 NIMH grant for a six-week clinical trial of robot-delivered CBT practice.

**Framework papers to cite from memory:**

- Fasola & Matarić, *A Socially Assistive Robot Exercise Coach for the Elderly*, JHRI 2(2):3–32, 2013 (https://robotics.usc.edu/publications/793/). n=33 older adults, four 20-minute sessions, between-subjects: 16 physical robot, 17 computer simulation of the same robot. **Five design principles** for any SAR therapeutic intervention: (1) motivating, (2) fluid and highly interactive, (3) personable, (4) intelligent, (5) task-driven. Embodiment results, physical over virtual: enjoyableness t(31)=2.29, p<.03; value/usefulness t(29)=2.72, p=.01; helpfulness t(31)=2.66, p=.01; social attraction t(30)=2.09, p<.05; social presence t(23)=2.59, p<.02. Non-significant same-direction trends: companionship p<.08, intelligence p<.06, exercise partner p=.07.
- Deng, Mutlu & Matarić, *Embodiment in Socially Interactive Robots*, 2019 (https://arxiv.org/abs/1912.00312). Reviews 65 studies (2003–2017) around "When and why should embodied robots be used instead of simpler and cheaper virtual agents?" The monograph does **not** deliver a blanket yes — quote the question, not a false answer.
- Shi, Landrum, O'Connell, Kian, Pinto-Alva, Shrestha, Zhu & Matarić, *How Can Large Language Models Enable Better Socially Assistive Human-Robot Interaction* (https://arxiv.org/html/2404.00938). Three opportunity categories: natural-language dialogue, multimodal user understanding, LLMs as robot policies. Risks named: hallucination, obsolete information, latency, disengagement cues, bias amplification, data security and privacy. Load-bearing sentence: **trustworthiness of LLM-powered SAR "needs to be extensively evaluated" before autonomous deployment with vulnerable populations.**

**What her lab measures as success — this should drive Helpee's software:**

1. **Objective, robot-logged per-session performance.** In the exercise study: average time to gesture completion, seconds per exercise, failed exercises, number of prompts the robot had to issue because the user wasn't moving, **feedback percentage**, total exercises completed (M=103.59 per session), breaks taken.
2. **Validated or adapted psychometrics.** Enjoyableness, value/usefulness, helpfulness, perceived intelligence, social attraction, social presence, and **companionship adapted from the Companion Animal Bonding Scale** (Poresky et al., 1987), chosen specifically "to assess potential user acceptance of the robot as an in-home companion."
3. **Clinical outcomes** in newer trials: psychiatric distress, anxiety, adherence, intrinsic motivation.
4. **Trajectory over time, not endpoint.** The Kian headline is an interaction effect across 14 days. Direction of change *is* the result.
5. **Disclosure intimacy** as a measured construct.

Synthesis: her lab's unit of credibility is a **logged per-session time series paired with a validated scale, reported as change over weeks.** Build that and the demo speaks her language.

---

## B. Evidence base: what is real versus what is marketing

| Intervention | Design | Outcome and effect | Source |
|---|---|---|---|
| **PARO robotic seal** | Cluster RCT: 9 facilities PARO, 10 plush toy with robotics **disabled**, 9 usual care; 15-min sessions 3×/week × 10 weeks | PARO beat usual care on agitation (CMAI-SF) and pleasure. PARO **and the plush toy** both beat usual care on reducing neutral affect. PARO beat the plush toy **only on engagement.** | Moyle et al., JAMDA 2017 — https://pubmed.ncbi.nlm.nih.gov/28780395/ |
| PARO, group-based | RCT, mild dementia | Improved cognition; alleviated loneliness and depression | https://www.sciencedirect.com/science/article/abs/pii/S1525861024006509 |
| PARO, pooled | Meta-analysis, 3 trials, n=214 | Pet-type robot improved agitation | https://www.sciencedirect.com/science/article/abs/pii/S0197457219305257 |
| **Social robots for loneliness** | Meta-analysis, 19 studies, 42 effect sizes, N=1,083, 2003–2024 | **d = −0.590, 95% CI [−0.919, −0.261], p<.01.** With control groups d=−0.878, **95% CI [−1.71, 0.042] — crosses zero.** Egger's β=−0.825, p<.01 → **publication bias detected** | Mehrabi & Ghezelbash, *The Gerontologist* 65(12), 2025 — https://pmc.ncbi.nlm.nih.gov/articles/PMC12598933/ |
| Social robots in long-term care | Meta-analysis of RCTs | Depression and loneliness | https://www.sciencedirect.com/science/article/abs/pii/S1525861024001762 |
| **Joy for All robot pet** | Pilot RCT | Intervention arm significantly more likely to be in the **top quartile of positive affect** at follow-up | https://www.ajgponline.org/article/S1064-7481(25)00558-5/fulltext |
| Joy for All | 8-month stepped-wedge cluster RCT, care homes | Neuropsychiatric symptoms, challenging behaviour, communication, loneliness | https://clinicaltrials.gov/study/NCT04168463 |
| Robotic companion pets | Dementia, COVID era | Reduced depression and loneliness | Fogelson et al. 2022 — https://pubmed.ncbi.nlm.nih.gov/34889146/ |
| **ElliQ / NYSOFA** | 3-year state program, non-randomized, vendor-measured | 834 enrolled (3,500+ applied), mean age 75, 80% female. **41 average interactions/day, up from 29 in year 2.** CSAT 4.6/5. 94% "say they feel less lonely," 97% "feel better overall." Wellness Coach: **60% retention at 3 months.** Activity mix: companionship 40.1%, cognitive 19%, wellness 15.1%, health 11%, tools/reminders 8.9%, infotainment 3.8%, social connectedness 2%. | https://aging.ny.gov/system/files/documents/2026/02/nysofa-elliq-project-update-2026.pdf |
| **LLM SAR vs LLM chatbot** | N=26, 14 days daily CBT in residences | Engagement and disclosure intimacy **rose** with the robot, **fell** with the chatbot | https://arxiv.org/abs/2506.17831 |
| SAR exercise coach, physical vs virtual | n=33 older adults, 4 sessions | Physical robot preferred on 5 of 5 hypothesized measures | https://robotics.usc.edu/publications/793/ |
| Long-term in-home SAR | MoveCare, older adults living alone | >300 weeks cumulative usage; separate 130-week deployment across 10 apartments | https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8853423/ |

**The honest read on effect sizes.** Pooled d of −0.59 looks strong, but: publication bias is statistically detected; the controlled-studies subset has a CI including zero; and **robot type — pet, humanoid, or voice assistant — did not moderate the effect**, nor did duration. Institutional settings showed larger effects than independent living (the opposite of Helpee's home target), and US effects were smaller than Japan's/Turkey's.

That null moderator is the most dangerous finding for Helpee: **on loneliness alone, there is no published evidence that a sophisticated robot beats a $100 plush cat.** The PARO trial makes the same point from the other side. So loneliness reduction is the wrong headline claim. The defensible claims are what a plush cat structurally cannot do: sustained proactive engagement, reminder adherence, fall escalation, connection to a human. Measure those separately.

**The honest read on ElliQ.** The engagement data is genuinely the best longitudinal dataset in consumer SAR: 41 interactions/day sustained across a program year, rising year over year, 60% retention on self-set goals at three months. Cite that for engagement durability. But the wellbeing numbers come from the vendor-built "Cobot scale," single-item self-report, no control group. "94% feel less lonely" is not an effect size. Use ElliQ for engagement, the meta-analysis for loneliness effects, never blend them. (Data caveat: the report's four monthly participation rates — 26%, 81%, 88%, 92% — have a scrambled text layer in the PDF; re-check before quoting.)

---

## C. Aerial and floating HRI, including GT-MAB

### GT-MAB (Georgia Tech Miniature Autonomous Blimp)

Yao et al., *Autonomous flying blimp interaction with human in an indoor space*, FITEE 20(1):45–59, 2019 — https://jzus.zju.edu.cn/article.php?doi=10.1631/FITEE.1800587

- Explicitly designed **to support HRI experiments indoors for up to two hours** — endurance is the stated design purpose, the blimp's case against quadrotors in one line.
- "**GT-MAB is safe while flying in close proximity to humans.**"
- Detects a human's face, follows them, recognizes hand gestures via an **SSD deep network jointly detecting face and hands** in real time from a single onboard monocular camera. **The human wears no tracking device.**
- Two gestures recognized; the blimp responds with **distinguishable flight patterns** — motion as a communicative channel.
- "**The blimp communicates its intentions to the human user by displaying visual symbols**" (onboard display).
- Headline HRI result: "**visual feedback from the blimp in reaction to the human user significantly improves the interactive experience.**"
- Lab video page: "Using only one on-board monocular camera, GT-MAB is able to detect the human face and **keep a constant distance away from the human.**"
- Lineage: monocular human-following (https://ieeexplore.ieee.org/document/7989369/), blimp swarm (https://arxiv.org/abs/2505.09511), OpenBlimp.

*Confidence caveat: full text paywalled; abstract + video descriptions only. User-study N, instruments, detection accuracy, and dimensions need library access.*

### Cuddle-Fish — the closest published relative, read in full

Xu, Shao, Ju et al. (Keio), *Cuddle-Fish: Exploring a Soft Floating Robot with Flapping Wings for Physical Interactions*, Augmented Humans 2025 — https://arxiv.org/abs/2504.01293

Hardware: helium envelope of aluminium-coated nylon film, **1.0 m × 0.45 m × 0.33 m, total mass 70 g**, two 3 g servos driving flapping wings, ESP32, 3.7 V 180 mAh LiPo. Flap 0.3–1.5 Hz. Wingspan adjustable **45–78 cm specifically to fit 70–90 cm interior doorways**. Altitude via internal moving mass; yaw via differential flapping. Named binding constraint: **helium lifts ~1 g/L.**

User study: N=24, ages 22–35, Wizard-of-Oz, six maneuvers.

- **22 of 24 (92%) spontaneously engaged in touch** — patting, stroking, hugging, cheek-touching. Unprompted.
- **Four participants (17%) showed avoidance** — with a 70 g soft robot. Psychological safety is not automatic even in the safest hardware class.
- Valence rose significantly (Z=−3.76, p<.001); arousal unchanged.
- **Spin Overhead was the worst-rated maneuver** by a wide, significant margin.
- Their quadrotor critique: propellers/rigidity/noise create risk; prior work found people felt unsafe around small quadrotors **even with prop guards.**

Caveat: participants were 22–35. Nobody has run this with elders.

### Floating Companion — the design-space paper

DIS 2026 (Keio + MIT Media Lab) — https://dl.acm.org/doi/10.1145/3800645.3813051. Experts highlighted soft floating robots for **emotional support and companionship, specifically loneliness** — "a sense of a living being in the room." Envisioned roles: caretaker, assistant, comfort partner, telepresence avatar; reminders. Design references: Tinker Bell, Mew, Soot Sprites. **Strategic note: two weeks old in press terms — Helpee is now an instance of a named emerging class ("soft floating robots"), far easier to defend academically than a one-off.**

Earlier lineage: Floating Avatar (SIGGRAPH 2011), ZeRONE (CHI 2019), Emoballoon.

### Drone proxemics — the numbers

*Preferred Distance in Human–Drone Interaction*, Vision 8(4):59, 2024 — https://pmc.ncbi.nlm.nih.gov/articles/PMC11503297/

- **Grand mean preferred distance 1.84 m** (Exp 2: 1.62 m) — **roughly double human-human distance (~1 m), d≈1.0.**
- Vertical tolerance is **C-shaped**: closest around waist height; more distance demanded above eye level and at lower-leg level.
- **Anthropomorphic features increased demanded distance.**
- Recommendations: operate at or below eye level where possible; be deliberate about anthropomorphic features.

Supporting: Duncan & Murphy comfortable passing distance 0.6–0.9 m; Yeh et al. HAI 2017 (https://dl.acm.org/doi/10.1145/3125739.3125773) — **socially-shaped design + greeting voice decreased acceptable distance**; THRI cross-modality study (https://dl.acm.org/doi/10.1145/3675757) — different study modalities produce different distances.

### The one aerial-eldercare study

*Feeling of Safety and Comfort towards a Socially Assistive UAV That Monitors People in a Virtual Home* — https://pmc.ncbi.nlm.nih.gov/articles/PMC7866270/. VR, N=60 incl. **23 older adults (M=74.5)**.

- **For monitoring: high altitude above the head strongly preferred and rated safest**, lowest distraction.
- Lower/medium velocities safer. **Constant-radius circular trajectories preferred**; paths near the face = "too much supervision."

**The synthesis that reads as research-literate:** lab proxemics says "at or below eye level" (conversation); in-home monitoring says "above the head" (ambient). The resolution is task context → **two explicitly separate spatial modes with a legible transition**: conversational mode ≈1.5–1.8 m at/just below eye level with vocal announcement before approach; ambient mode above head height at constant radius. **Never spin overhead.**

### Noise — the hardest technical objection

- **UAV noise is more annoying than road/aircraft noise at matched loudness** (n=38) — https://www.sciencedirect.com/science/article/abs/pii/S0022460X20304818
- Predictors: loudness, sharpness, fluctuation strength, tonality.
- Killer finding: "**UAS sounds are more annoying and noticeable in a quieter, calmer acoustic environment**" — https://www.nature.com/articles/s44384-024-00001-6. A quiet living room is the worst case.
- Older adults' speech-in-noise deficits mean self-noise degrades the robot's own intelligibility.
- Strongest argument for buoyant lift. Commit to a measured dBA at 1 m, not an adjective.

### Older adults and drones generally

*Human-Drone Interaction in Older Adults: A Systematic Review*, Drones 10(5):389, 2026 — https://www.mdpi.com/2504-446X/10/5/389. Favourable perceptions for health/support/safety; barriers in usability, trust, interaction design. Baseline: **one-third of assistive technologies abandoned within one year.** *(MDPI 403; summaries only.)*

---

## D. Design guidance: persona, anthropomorphism, privacy

### Anthropomorphism and form

- **Uncanny valley applies to animals; the failure mode is mixing registers.** Löffler et al., HRI 2020 (https://dl.acm.org/doi/10.1145/3319502.3374788): U-shaped likeability; predictors of falling in = visible joints, **presence of a pupil**, **presence of a snout**. Commit fully to abstract-stylized or fully to a coherent creature.
- **Age inverts it:** older adults showed no uncanny valley and preferred humanlike robots (https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6840491/). A young designer's instincts are not the target user's.
- **Faces cost personal space** (proxemics above): expressive but non-facial channels (light, motion, sound) at close range.
- Frontiers 2025 (https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2025.1622206/full): face/mouth/eyes signal social capability but too-humanlike causes discomfort; cultural variation is substantial.

### Voice and persona for older adults

| Do | Evidence |
|---|---|
| Slow speech rate; slower still for instructions | Older adults expect systems to respond more slowly, especially instructional — https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10132265/ |
| High-quality neural TTS, never robotic | Presbycusis strips high-frequency consonants; older adults understand synthetic speech worse — https://www.cstr.ed.ac.uk/downloads/publications/2012/08-vipperla-2013.pdf |
| Barge-in + back-channeling | Matarić's own 2025 SLM study participants valued natural turn-taking and back-channeling; TalkTive — https://arxiv.org/abs/2202.08216 |
| Paraphrase bank per intent, randomized | Fasola's "Intelligent" principle: 10+ phrasings per praise intent |
| Continuity behaviours | Fasola's "Personable" principle: name at greeting/farewell, reference last + next session, past performance |
| Voice personalization (rate, complexity); visual pairing | Frontiers 2025 |
| Response speed + feedback clarity | Reduces technological anxiety; https://arxiv.org/abs/2203.15767, https://arxiv.org/abs/2409.08449 |

### Childlike/pet framing: the real trade

**For:** best-evidenced form for affect (PARO, Joy for All); invites touch (92% in Cuddle-Fish); honest low expectations.
**Against:** Sharkey & Sharkey's **infantilisation** charge; Sparrow's deception argument.
**The useful nuance (Sharkey's own):** "the possible willing collusion of the elderly with such deception" → rule: **never claim to be alive or to feel; answer "are you real?" honestly and identically every time; don't lecture someone out of a fiction they've chosen.** Safest register: a **companion appliance with a personality** — pet-like in motion, machine-honest in speech.

### The ethics literature to name

Sharkey & Sharkey, *Granny and the robots* — https://link.springer.com/article/10.1007/s10676-010-9234-6. Six concerns: (1) **reduced human contact** ("Robots could provide an excuse for such neglect"); (2) objectification; (3) privacy; (4) liberty; (5) deception/infantilisation; (6) responsibility. Verdict: "It is not the use of robots in elder care per se that should concern us, but the ways in which they are used." Recommendations include guidelines on **how long a person may be left alone with a robot** and **permission before physical interaction**.

**The sentence aimed at Helpee's form factor:** a robot's "personable, or animal-like appearance" may lead it to be welcomed "where for instance a surveillance camera would not be accepted." **Cuteness smuggles in surveillance.** Name it first; answer with architecture — consent re-earned explicitly, not inherited from charm.

### Privacy: what elders actually accept

*Barriers and Facilitators to Older Adults' Acceptance of Camera-Based AAL*, Innovation in Aging 9(2) — https://academic.oup.com/innovateage/article/9/2/igae100/7914012 — 50 studies, 28 barriers, 19 facilitators.

**Barriers:** privacy first — elders felt "watched," and **sabotaged systems (obstructing lenses, hiding behind furniture)**; stigma/identity ("dependency and deterioration" framing); obtrusiveness; lack of perceived need; cost; **false alarms creating burdens.**
**Facilitators:** reliably summoning help; genuine perceived need (post-fall); **blurred/anonymized processing** ("it's essential it's blurred"); **decisional control** over who accesses what and when; **avoiding institutionalization** — elders trade privacy to stay home.
**Rejected outright:** standard RGB cameras; family using data for premature care decisions; deficit framing.
**Rooms:** living room/kitchen accepted, bedroom less, bathroom least — except some accept bathroom coverage precisely because fall risk peaks there. Corroborated: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12736577/, Cambridge scoping review, PIR+LiDAR bathrooms (https://arxiv.org/abs/2505.18242).
**Permissions UI mapping:** per-recipient permissions **including forbidding family while granting professionals**; motion/time-windowed capture; identity protection.

### Autonomy vs surveillance

Frontiers 2025: **user-adaptable autonomy level**. ElliQ precedent: "Clients are in control of the information they share... opt out at any time." Sharkey: permission before physical interaction.

### Abandonment — what kills companion robots

- **One-third of assistive tech abandoned within a year.**
- Across **70 in-home robot deployments (~6 months)**: people stopped for **lack of enjoyment and lack of perceived usefulness.**
- Novelty effect: short-term appeal does not predict long-term use (https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2022.733078/full).
- Long-term hosting study (https://ieeexplore.ieee.org/document/9889488/): usage drivers/killers = **guilt, proactivity and movement, expectation match, persona.** Proactivity/movement are engagement *drivers* (argument for a mobile companion); **guilt is a design hazard** — a robot that visibly waits manufactures obligation, and obligation is a reason people quit.
- Positive longitudinal counter-examples: ElliQ (41 interactions/day sustained) and Kian et al. (robot engagement rising over two weeks).

**The paper that should reshape success metrics:** Meng et al., *Beyond Usability: "Withdrawal Design"*, CHI '26 workshop — https://arxiv.org/abs/2606.16439. 8-week RCT, N=40 children with ASD: continued robot access **reduced anxiety** but was associated with **lower social motivation and weaker emotion-recognition gains** than withdrawal, despite SUS M=98. "**For vulnerable users, 'engagement' can mask ecological downsides**"; "**A robot designed as a bridge may instead become a preferred endpoint**"; success "should be judged not by retention, but by designed separation that bridges back to human relationships." Children not elders, but it is the sharpest critique of the retention metrics every companion company reports — volunteer it unprompted.

---

## E. The ten hardest questions, with literature-grounded answers

**1. Why embodiment? Why not a smart speaker?** Embodiment buys **durability of engagement and depth of disclosure over weeks** — the currency of a loneliness intervention. Kian et al. 2025 (her lab, same LLM, robot ↑ chatbot ↓); Fasola & Matarić 2013 (physical beat virtual on 5/5 measures). Honest caveat to volunteer: Deng/Mutlu/Matarić frame the benefit as conditional; "Voice Over Body?" found highly talkative older adults may prefer voice-only. The claim is not "robots are better" — it is "embodiment keeps a person engaged past the point where an app is deleted."

**2. Why aerial?** Be straight: **no published evidence that aerial beats tabletop for companionship.** What's supported: proactivity and movement drive sustained usage; mobility lets the companion follow the person's day; ground robots fail on thresholds/rugs/clutter and are trip hazards for exactly this population; GT-MAB proved the primitives (2-hour endurance, face-following, gestures); Cuddle-Fish drew unprompted touch from 92%; Floating Companion's experts named the class for loneliness. Frame aerial as **a testable hypothesis with a tabletop control** — proposing the study that could falsify your own thesis is the most credible thing an 18-year-old can do in that room.

**3. Noise?** UAV noise is more annoying than road noise at matched loudness; **worse in quiet environments** — a quiet living room is the worst case; self-noise degrades the robot's own speech intelligibility for presbycusic users. Answer: buoyancy — thrust only for correction, never support. Commit to a measured dBA at 1 m.

**4. What if it hits a frail person?** The class is safe: ~1 g/L lift means tens of grams; Cuddle-Fish is 70 g and soft; GT-MAB "safe in close proximity"; power loss = slow drift. **But physical safety ≠ psychological safety**: 17% avoidance with a 70 g soft robot; people felt unsafe around guarded quadrotors. Safety must be *legible* — announced approaches, predictable motion, visible intent.

**5. Spatial policy?** 1.6–1.84 m preferred distance (~2× human-human, d≈1.0); C-shaped vertical tolerance; anthropomorphic features increase distance; for monitoring, above-head constant-radius preferred (older-adult VR study). → **Two modes**: conversational ≈1.5–1.8 m at/below eye level with vocal announcement; ambient above head, constant radius. Never spin overhead. A greeting voice measurably *decreases* required distance — the greeting is functional.

**6. Cameras in an elder's home?** Accepted when: reliably summons help, genuine perceived need, blurred/anonymized, decisional control, keeps them out of a facility. Rejected: raw RGB, family overreach, deficit framing, **false alarms**. Rooms: living/kitchen yes, bedroom less, bathroom least (with the fall-risk exception). Design: on-device processing, pose/blurred only, no-sense zones, per-recipient permissions, and Sharkey's "cuteness smuggles surveillance" treated as a hard constraint.

**7. Replacing human contact? Deception?** Name Sharkey's six concerns first; bring the withdrawal RCT. Product commitment: **success metrics include human-contact outcomes** — calls placed, visits arranged; rising Helpee usage with falling human contact = defined failure. Deception: never claim to be alive; answer "are you real?" identically every time; per Sharkey's nuance, don't argue someone out of a chosen fiction.

**8. Human subjects at 18 with no affiliation?** *(Domain knowledge — verify with USC OPRS.)* Prospective studies of monitored elders = human-subjects research under 45 CFR 46; IRB approval cannot be retroactive. Pre-IRB legitimate: engineering validation on self/household adults; expert interviews; VR/simulation with young adults (exactly what the literature did). At USC: join a faculty-supervised protocol — **a concrete, non-sentimental reason to want the lab affiliation; say it out loud.** IRB concerns: capacity screening, LAR consent, duty-to-act/mandatory-reporting on falls and suicidal ideation, data security, adverse-event and stopping plan.

**9. Credible pilot?** Field norms: her studies are N=11–33, multi-session. → **N≈12–20, 6–8 weeks** (clears novelty). **Control matters most**: "no robot" proves nothing (plush-toy arm matched PARO; robot type doesn't moderate loneliness). Compare against a smart speaker running the same LLM, or stationary Helpee. Primary: **UCLA Loneliness Scale** (17 of 19 meta-analysis studies). Secondary: GDS-15/PHQ-8, logged adherence, engagement time series, human-contact measure. Pre-register; report the **time × condition interaction**.

**10. Your LLM hallucinates medication advice — then what?** Her lab's survey names hallucination/latency/privacy as unresolved and demands extensive evaluation pre-deployment; HRIBench shows VLMs struggle at real-time perception. Answer with architecture: **no generative model in the safety path.** Medication content, escalation logic, contacts = deterministic templates; LLM = open conversation only; refusal-and-handoff rails for medical questions; auditable transcript with model version and latency per turn.

**Two more likely and awkward:**

**Why not a $100 Joy for All cat?** On loneliness alone, it might be. Differentiators = what a plush cat structurally cannot do: proactive reminder adherence, fall escalation, connecting to a human — each measured separately.

**Evidence this helps vs. evidence people like it?** "None of my own yet, and here's the instrumented system that will produce it" — exactly what a lab needs and cannot easily buy.

---

## F. Software features that make the demo research-credible

1. **Session-level event log as the primary data structure** — timestamp, initiator (robot vs user), duration, modality, intent, completion, outcome. *(Fasola maps principles to logged measures.)*
2. **Engagement dashboard showing trajectory, not totals** — sessions/day, session length, **user-initiated share**, latency, turns, disclosure depth; time series with trend + week-6 marker. *(Kian is an interaction-over-time result.)*
3. **Real adherence tracking** — per reminder: delivered/acknowledged/completed/snoozed/missed, **prompts required**, time-to-completion; per-category rates + 7-day trend. *(Fasola's "prompts required" idiom; ElliQ caregiver alerts.)*
4. **Standardized scales on two cadences** — daily 1-item mood/loneliness probes in conversation; UCLA-LS (3-item routine, 20-item for publication) + PHQ-2/GDS-15 every 2–4 weeks; item-level storage. *(UCLA-LS = 17 of 19 studies.)*
5. **Anti-repetition engine with a metric** — paraphrase bank per intent, sampled without replacement, "repetition rate" surfaced. *(Fasola: 10+ phrasings per intent.)*
6. **Visible continuity and memory** — Fasola's four callbacks + an inspectable memory view (doubles as privacy feature).
7. **Privacy as a feature** — on-device perception, no raw video egress, sensing-state indicator, no-sense zones (bed/bath default-off), **per-recipient permission matrix**, resident-readable audit log, one-touch pause. *(Maps to the 50-study review's facilitators.)*
8. **Staged escalation with a published false-alarm budget** — ladder with dwell times, easy "I'm fine" cancel, every escalation logged vs ground truth; **false alarms/week as a headline number.** *(False alarms cause outright rejection.)*
9. **Human-contact outcome tracking — the anti-substitution metric** — calls/messages/video facilitated, visits arranged, self-reported contact hours; rising engagement + falling contact = failure. *(Sharkey #1; withdrawal study. Nobody commercial measures this.)*
10. **Deterministic safety path, architecturally separate from the LLM.**
11. **Spatial policy in software** — mode variable, target distance/altitude per mode, mandatory vocal announcement, logged distance/altitude histograms. *(The aerial-HRI safety case artifact.)*
12. **Latency instrumentation** — p50/p95 time-to-first-audio; barge-in + back-channel support.
13. **Voice configuration first-class** — rate (slower default, slower for instructions), volume, verbosity, "say that again."
14. **Abandonment early-warning composite** — declining initiation + shortening sessions + rising missed reminders → per-user risk indicator. *(The two universal quit reasons surface here weeks early.)*
15. **Data export + synthetic-data harness** — one-command CSV/Parquet with codebook; demo mode with realistic synthetic longitudinal data. *(Idiomatic to her lab — they publish synthetic-user harnesses.)*

---

## Confidence notes

Paywalled/blocked (abstract/press only): GT-MAB full text; Floating Companion DIS 2026; Drones 10(5):389; Science Robotics embodiment-debate piece (https://www.science.org/doi/10.1126/scirobotics.aed4569); Matarić's ICMI keynote. Read in full: Fasola & Matarić 2013, Cuddle-Fish, NYSOFA ElliQ 2026, Sharkey & Sharkey, withdrawal-design paper. The IRB answer is domain knowledge, not a fetched source.

Two prep notes: (1) *The Illusion of Intervention* means **never bring LLM-simulated user results as evidence** — her group is publishing the argument against them right now. (2) HRIBench means vision-language claims should be conservative: "here is what I measured on my hardware."
