# Research 03 — Regulatory & Compliance Landscape (US, July 2026)

> Produced 2026-07-25 by the regulatory research agent. Part of the Helpee
> pre-build research phase. See docs/RESEARCH.md for the synthesis.

**Scope note on confidence:** Items marked ⚠️ **verify with counsel** are a reading of statutory text or an inference from adjacent precedent rather than a settled holding. Everything else is directly supported by the cited source. Two widely-repeated claims turned out to be **false** and are corrected below (Apple Watch fall detection; "general wellness" as the shield for fall alerts).

---

## A. Verdict: is v1 a medical device?

**Short answer: almost certainly not a *premarket-regulated* device — but not for the reason most people assume, and one of v1's four functions sits inside FDA's device taxonomy as a 510(k)-EXEMPT Class II device.**

FDA regulates **by software function**, not by product, so Helpee has to be sliced into four and analyzed separately ([FDA, Device Software Functions incl. Mobile Medical Applications](https://www.fda.gov/medical-devices/digital-health-center-excellence/device-software-functions-including-mobile-medical-applications)).

### 1. LLM conversation / companionship → not a device
No diagnosis, cure, mitigation, prevention, or treatment intent, so it fails the device definition at FD&C Act § 201(h). This function is unregulated *by FDA* — but it is squarely regulated by the new state AI-companion laws (see §F, Risk 2). This is the one function where FDA is the *wrong* thing to worry about.

### 2. Medication reminders → device definition arguably met, but explicit FDA enforcement discretion
FDA exercises enforcement discretion for software that helps users "adher[e] to pre-determined medication dosing schedules by simple prompting" ([FDA enforcement-discretion examples](https://www.fda.gov/medical-devices/digital-health-center-excellence/device-software-functions-including-mobile-medical-applications)). **This holds only while the reminder is dumb.** The moment Helpee calculates a dose, changes timing based on inferred symptoms, or interprets adherence data clinically, it leaves the discretion zone.

### 3. Voice check-ins / mood & activity logging → general wellness
Fits the two-factor test in FDA's **January 2026 revised** *General Wellness: Policy for Low Risk Devices*: (i) intended use is maintaining/encouraging general health, and (ii) the product is noninvasive, non-implanted, and poses no technology-based safety risk ([Troutman analysis](https://www.troutman.com/insights/fdas-2026-guidance-on-general-wellness-devices-policy-for-low-risk-devices/); [Covington](https://www.cov.com/en/news-and-insights/insights/2026/01/fda-issues-revised-guidance-on-general-wellness-products)).

### 4. Camera-based fall detection + escalation → this is the real question

**Correction to a common assumption:** "General wellness" is the **wrong shield** for fall alerting. The 2026 guidance is built around *physiologic-parameter measurement for lifestyle purposes*, and it expressly excludes products whose outputs "prompt or guide specific clinical action" or provide "ongoing monitoring or alerts for medical management" ([Arnold & Porter](https://www.arnoldporter.com/en/perspectives/advisories/2026/01/fda-cuts-red-tape-on-clinical-decision-support-software)). Summoning help for a person on the floor isn't a wellness claim at all — it's a safety function, and FDA has a dedicated home for it.

**The actual classification.** FDA's mobile-app guidance places apps that "enable a patient or caregiver to create and send an alert or general emergency notification to first responders" — and apps that initiate a pre-specified **nurse call** — under:

| | |
|---|---|
| Product code | **ILQ** |
| Device name | System, Communication, Powered |
| Regulation | **21 CFR 890.3710** |
| Class | **II** |
| Premarket | **510(k) EXEMPT**, subject to 21 CFR 890.9 |

Verified against the FDA classification database rather than secondary sources: the openFDA record for ILQ returns `regulation_number: 890.3710`, `device_class: 2`, `submission_type_id: 4`. Calibration on that field: DXN (noninvasive BP) and FLL (continuous thermometer) both return `1` (510(k) required), while BZN (crash cart, indisputably exempt) returns `4`. So **4 = exempt**. This matches the CFR text at [21 CFR 890.3710](https://www.law.cornell.edu/cfr/text/21/890.3710): Class II and "exempt from the premarket notification requirements... subject to § 890.9."

**Two things follow, and they pull in opposite directions.**

*The good news:* no 510(k), no clinical trial, no predicate hunt.

*The catch:* [21 CFR 890.9](https://www.law.cornell.edu/cfr/text/21/890.9) voids the exemption if a device "is intended for a use different from" legally marketed devices of that type **or** "operates using a different fundamental scientific technology." ⚠️ **Verify with counsel:** a camera + neural network performing *automatic, unprompted* fall detection is a genuinely arguable "different fundamental scientific technology" from a pendant with a button. This is the single sharpest unresolved FDA question in v1.

**What market practice says.** The counterweight is strong and eight years long:

- **SafelyYou** runs camera-based AI fall detection across memory-care facilities at scale and registered its NIH-funded trial with **"FDA Regulated Device: No"** ([NCT03685240](https://clinicaltrials.gov/study/NCT03685240)). FDA has never challenged it.
- **Apple Watch fall detection was never FDA-cleared.** Widely misreported — [Forbes](https://www.forbes.com/sites/jeanbaptiste/2018/09/14/apple-watch-4-is-now-an-fda-class-2-medical-device-detects-falls-irregular-heart-rhythm/) and [MobiHealthNews](https://www.mobihealthnews.com/news/apple-watch-series-4-will-have-fda-cleared-ecg-fall-detection) both say it was, and both are wrong. Apple's only De Novo grants were **DEN180044** (ECG app) and **DEN180042** (irregular rhythm notification). Fall detection shipped as an unregulated safety feature.
- **Vayyar Care** markets radar fall detection to senior living touting **FCC** approval and says nothing about FDA ([Vayyar](https://vayyar.com/care-docs/b2c/)).

**Bottom line:** the entire category operates on the premise that automatic fall detection + caregiver notification is not a premarket-regulated device, and FDA has acquiesced for years. Ship v1 on that basis. But the exemption is a *premarket* exemption only — see §C on what still applies — and the "no auto-911 in v1" decision is doing far more regulatory work than it may appear: it keeps Helpee outside FDA's own worked example ("...to **first responders**") and outside the nurse-call example. **Protect that boundary deliberately.**

### The LLM-decides-escalation question: do NOT reach for the CDS exemption

The Clinical Decision Support pathway is **unavailable**. FDA's 2026 CDS guidance (issued Jan 6, 2026, replacing the 2022 version) keeps the statutory Criterion 3 from FD&C Act § 520(o)(1)(E): the software must support **health care professionals**. Software providing recommendations to **patients or caregivers is a device**, full stop ([Faegre Drinker](https://www.faegredrinker.com/en/insights/publications/2026/1/key-updates-in-fdas-2026-general-wellness-and-clinical-decision-support-software-guidance); [Crowell](https://www.crowell.com/en/insights/client-alerts/fda-issues-final-guidance-on-clinical-decision-support-software)). Separately, **time-critical alarms remain devices** because urgency defeats the independent-review requirement in Criterion 4, and FDA's 2026 update leans harder on transparency and automation bias — a black-box LLM is precisely the profile FDA flagged.

**Design consequence — the most important architectural point in the report:** frame escalation as **routing a non-clinical event**, not clinical triage. Helpee should emit *"no movement detected for 4 minutes in the bedroom"* and route it to a human. It must never emit *"possible hip fracture,"* *"resident is deteriorating,"* or a **clinical urgency ranking**. The instant the LLM sorts events by medical severity for facility nurses, you are HCP-facing CDS with a black-box algorithm — the worst regulatory position available.

---

## B. Marketing language: forbidden vs. safe

FDA judges intended use largely from **labeling, website, sales deck, and app-store copy**. Founder tweets count. This is the cheapest and most commonly blown compliance item.

### ❌ Never use

| Forbidden | Why |
|---|---|
| "Medical device," "FDA-approved," "FDA-cleared," "clinically proven" | False; "approved" is wrong even for cleared devices |
| "Monitors patient health," "patient monitoring," "remote patient monitoring" | "Patient" + "monitoring" is the classic intended-use trigger; RPM is a reimbursed clinical category |
| "Detects/diagnoses stroke, dementia, Alzheimer's, UTI, sepsis, delirium" | Disease-specific claims are dispositive ([Troutman](https://www.troutman.com/insights/fdas-2026-guidance-on-general-wellness-devices-policy-for-low-risk-devices/)) |
| "Prevents falls," "reduces fall risk," "fall risk assessment" | Prevention/mitigation of a condition = device intent |
| "Abnormal," "pathological," "diagnostic," "clinical threshold" | Named as device-triggering categorizations |
| "Calls 911," "emergency dispatch," "alerts first responders" | Lands inside FDA's ILQ worked example — the one line v1 is built to avoid |
| "Replaces a caregiver / nurse / check-in visit," "24/7 medical supervision" | Substitution claim; also indefensible in litigation |
| "Never misses a fall," "guaranteed," "99% accurate" | Overpromising is what sank the PERS defendant in §E |
| "HIPAA-certified," "HIPAA-compliant device" | No such certification exists; regulators treat this as deceptive |

### ✅ Safe

- "Companion robot for older adults" / "friendly presence at home"
- "Conversation, company, and gentle reminders"
- "Medication **reminders**" — always the noun *reminder*, never *management* or *administration*
- "Helps your family stay connected and informed"
- "Sends a notification to your family if it sees something that may need attention"
- "Peace of mind for families"
- "**Not a medical device. Not a substitute for professional medical care, supervision, or emergency services.**" — footer, box, onboarding flow, and terms

### The nuance worth exploiting
The 2026 guidance **permits** a general notification "when the user's outputs fall outside of certain ranges, informing the user that an evaluation by an HCP may be helpful," provided there's no disease reference and no clinical-action guidance ([Arnold & Porter](https://www.arnoldporter.com/en/perspectives/advisories/2026/01/fda-cuts-red-tape-on-clinical-decision-support-software)). So *"You've been sleeping less this week — it might be worth mentioning to your doctor"* is fine. *"Your sleep pattern suggests early cognitive decline"* is a device claim and probably also a lawsuit.

### The vitals roadmap — one genuinely good surprise
- **Blood pressure:** FDA **reversed** its mid-2025 position in the January 2026 guidance and now permits noninvasive products that measure or estimate BP to qualify as **general wellness**, if claims stay strictly wellness-focused ([Covington](https://www.cov.com/en/news-and-insights/insights/2026/01/fda-issues-revised-guidance-on-general-wellness-products)). A real opening that did not exist twelve months ago. The regulated alternative is product code **DXN**, [21 CFR 870.1130](https://www.accessdata.fda.gov/cdrh_docs/pdf24/K241578.pdf), Class II, **510(k) required**.
- **Temperature:** harder than BP, and the trap is specific. FDA exempted general clinical electronic thermometers from 510(k) in a [June 18, 2025 final order](https://www.federalregister.gov/documents/2025/06/18/2025-11207/medical-devices-exemptions-from-premarket-notification-class-ii-devices-clinical-electronic) but **expressly carved out continuous-measurement and telethermographic** devices. Product code **FLL** is now "Continuous Measurement Thermometer" (21 CFR 880.2910, Class II) and the openFDA query returned `submission_type_id: 1` — **510(k) required**. A camera-based or continuous temperature feature is exactly the carve-out. Non-contact IR thermal imaging is telethermographic. **Assume 510(k) for temperature; BP may be free.** That's the opposite of most people's intuition.

---

## C. Bake into the software NOW

Ordered by cost-of-retrofit. Items 1–4 are 10x cheaper to build now than to bolt on during a facility's security review.

### 1. Consent & recording state machine — highest retrofit cost
- Per-**person** consent records (not per-device): subject, scope (audio / video / clip-retention / cloud), timestamp, method, consenting party, and **whether that party is the resident or a surrogate** with the legal-basis field populated.
- **Roommate consent** as a first-class object with its own lifecycle. Required by state granny-cam statutes in shared rooms ([Bedsore.Law](https://www.bedsore.law/room-cameras-in-nursing-homes-consent-evidence-and-state-rules/)).
- **Capacity/surrogate chain** mirroring [210 ILCS 32/](https://law.justia.com/codes/illinois/chapter-210/act-210-ilcs-32/): resident → guardian → health care agent → representative → spouse → parent → adult child.
- **Visitor/third-party mode:** a one-tap "guests present" pause, plus an audible + visible announcement when anyone unenrolled is detected. This is the Illinois/California audio defense — see §D.
- **Instant revocation** that is *architecturally* enforced (kills the pipeline), not a UI flag the inference loop can ignore.
- **Privacy pause** for personal care, bathing, and dressing — anti-retaliation and pause-on-request provisions are standard in these statutes.

### 2. Immutable audit log
Append-only, tamper-evident, exportable. Log every: consent grant/revoke, clip creation/access/export/deletion, escalation fired with full decision inputs, escalation **acknowledged by a human** (with identity and latency), config change, admin access, model/prompt version change. Required for HIPAA § 164.312(b) and it is the artifact that will actually decide a failure-to-escalate lawsuit — the version where the log shows *"notified daughter 14s after event, delivered, unacknowledged 47 min"* is a very different case from the version with no record.

### 3. Encryption + access control
AES-256 at rest, TLS 1.3 in transit, per-tenant key separation, MFA on all staff/admin accounts, RBAC scoped so facility staff see only their own residents, automatic session timeout, and **no PHI in logs, crash reports, or LLM telemetry**. The 2026 HIPAA Security Rule direction is toward mandatory MFA, encryption, and asset inventory, and toward BAs providing **annual written verification** of deployed safeguards — final action now targeted at **July 2027**, so build to it rather than waiting ([CBIZ](https://www.cbiz.com/insights/article/5-hipaa-security-rule-changes-in-2026-and-how-to-prepare); [Medcurity](https://medcurity.com/hipaa-security-rule-2026-update/)).

### 4. BAA-readiness
A signed BAA is table stakes the moment a facility engages ([HIPAA Journal](https://www.hipaajournal.com/hipaa-guidelines-on-telemedicine/)). Prepare now: a BAA template, a subprocessor inventory with **BAAs from every downstream vendor including the LLM provider** (a facility's security reviewer will ask specifically about this and it's the question that most often stalls deals), a written risk analysis, an incident-response runbook, workforce training records, and a **60-day breach-notification path to the covered entity** per 45 CFR § 164.410.

### 5. AI disclosure & crisis protocol — legally mandatory, not optional polish
Helpee meets both states' definitions of an AI companion. Build:
- **Spoken** AI disclosure at the start of every interaction — not buried in a EULA. Critical for cognitively impaired users, where "a reasonable person would be misled" is easiest to establish.
- **Recurring reminder every 3 hours** of continuing interaction. NY requires this for **all users**; CA requires it for minors ([Troutman Privacy](https://www.troutmanprivacy.com/2026/01/analyzing-the-new-ai-companion-chatbot-laws/)).
- **Self-harm/suicidal-ideation detection** with referral to crisis services (988), a hard block on generating self-harm content, and **logged referral counts** — CA reporting to the Office of Suicide Prevention begins **July 1, 2027**.
- Publish the protocol. CA requires it public.

### 6. Data minimization by design — borrow SafelyYou's architecture
SafelyYou **auto-deletes non-fall video within 60 seconds and records no audio at all** ([CITRIS](https://citris-uc.org/safelyyou-using-ai-to-detect-and-prevent-falls/)). Can't match the no-audio part, but mirror the discipline: local inference only, aggressive ring-buffer deletion, event clips opt-in and short (already the design — keep it), configurable retention with automatic purge, and **no raw audio ever leaves the base station**. Ship transcript-only, or better, extracted-state-only.

### 7. Breach notification for the consumer channel
Direct-to-family sales are **not** HIPAA-covered but **are** covered by the FTC **Health Breach Notification Rule** (16 CFR Part 318), whose amended final rule took effect **July 29, 2024** and expressly reaches health apps and **connected devices** ([FTC](https://www.ftc.gov/business-guidance/blog/2024/04/updated-ftc-health-breach-notification-rule-puts-new-provisions-place-protect-users-health-apps); [Federal Register](https://www.federalregister.gov/documents/2024/05/30/2024-10855/health-breach-notification-rule)). Notification is required for **unauthorized disclosure**, not just external breach — an accidental cross-tenant leak or an over-broad third-party SDK triggers it. ⚠️ **Verify with counsel:** also scope **Washington's My Health My Data Act**, which covers "consumer health data" broadly and carries a private right of action.

### 8. Model/version pinning
Record which model, prompt, and detection-threshold version handled every escalation. Without this you cannot investigate a miss, defend a suit, or satisfy the FDA transparency expectations that the 2026 CDS guidance signals.

---

## D. Facility-deployment blockers, ranked

### 🔴 1. Audio recording in shared rooms — the hardest blocker
Both target states are all-party-consent, and a facility room contains roommates, visitors, aides, nurses, and housekeeping who never consented.

- **Illinois** — [720 ILCS 5/14-2](https://codes.findlaw.com/il/chapter-720-criminal-offenses/il-st-sect-720-5-14-2/). **The rewritten statute is genuinely favorable.** After [*People v. Clark* and *People v. Melongo*, 2014 IL 114852](https://www.illinoiscourts.gov/Resources/75346741-ab67-410a-a7da-21b4c0123260/114852.pdf) struck the old Act as overbroad, the amended version requires **two** elements: the recording must be **surreptitious** *and* of a **private conversation** (defined at 14-1(d) as one where a party had a justified expectation of privacy) ([Reporters Committee](https://www.rcfp.org/reporters-recording-guide/illinois/)).
- **California** — [Penal Code § 632](https://www.shouselaw.com/ca/defense/penal-code/632/) reaches **"confidential communications."** Civil exposure of **at least $5,000 per violation** under § 637.2, with no injury required.

**Workaround — the design that unlocks the whole product:** engineer Helpee to be the *opposite* of surreptitious and to defeat the expectation of confidentiality. A 3-foot glowing blimp that **announces itself audibly on entering a room**, carries an always-visible recording indicator, posts doorway signage, and is disclosed in the admission packet is not plausibly "surreptitious," and a conversation held in front of an obviously-announcing robot is hard to characterize as confidential. Layer on: **no audio retention by default** (process locally, keep extracted state, discard the waveform), a hardware mute with a physically visible state, and auto-pause when an unenrolled voice is detected. ⚠️ **Verify with counsel per state** — a strong argument, not immunity; the analysis differs across the ~11 all-party states.

### 🔴 2. Illinois BIPA — the biggest financial tail risk, and it's avoidable
[BIPA § 10 (740 ILCS 14/10)](https://www.recordinglaw.com/us-laws/data-privacy-laws/bipa/) lists **voiceprints** and **scans of face geometry** as biometric identifiers. § 15(b) requires written notice and a signed release *before* collection; § 20 gives a **private right of action** at $1,000 negligent / $5,000 reckless-or-intentional. [SB 2979 (Aug 2, 2024)](https://www.kslaw.com/news-and-insights/illinois-bipa-reform-takes-effect) limited recovery to **one** per identifier-per-collection-method and the Seventh Circuit applied it retroactively ([Davis Wright Tremaine](https://www.dwt.com/blogs/privacy--security-law-blog/2024/08/illinois-bipa-biometrics-law-amended-for-damages)) — helpful, but per-resident × per-visitor × per-staff-member still compounds fast in a facility.

**The good news is a clean architectural line.** Ordinary video and pose/skeleton estimation that never builds a matchable template sits **outside** BIPA; the violation begins the instant software "analyses those frames to extract a face-geometry template and match it against a gallery" ([Fora Soft](https://www.forasoft.com/learn/video-surveillance/articles-vms/bipa-us-biometric-privacy-law)). Note that in [*Wilcosky v. Amazon*](http://blogs.duanemorris.com/classactiondefense/wp-content/uploads/sites/56/2023/11/Wilcosky-v.-Amazon-ECF-207-Order-Denying-MTD-11-1-23.pdf) an Alexa voiceprint claim **survived** a motion to dismiss.

**Workaround:** hard-prohibit face recognition and **speaker identification** in v1. Use pose/keypoint detection with no persistent identity template, and distinguish speakers by turn-taking or an explicit "who's talking?" prompt rather than by voice matching. If speaker ID is ever wanted, gate it behind BIPA-grade written consent with a published retention schedule. **Voice ID is the feature most likely to be proposed by an engineer and most likely to generate a class action** — write it into the architecture docs as forbidden.

### 🟠 3. Compressed helium in a healthcare facility — the blocker nobody sees coming
The most underrated item in the report; a facilities-department veto, not a legal one. **NFPA 99 § 11.3.3** permits up to **300 cubic feet** of nonflammable gas (~12 E-size cylinders) outside a storage enclosure per 22,500 sq ft; **300–3,000 cu ft must live in a secured noncombustible room** separated from combustibles, and ≥3,000 cu ft triggers full Chapter 5 construction and ventilation requirements ([Consulting-Specifying Engineer](https://www.csemag.com/back-to-basics-medical-gas-storage-under-nfpa-99/); [HFM](https://www.hfmmagazine.com/articles/4002-oxygen-tank-storage-regulations)). Helium is also a **simple asphyxiant** — a leak in a small room is a real safety review item.

**Workaround, and it's a strong one:** never put a helium cylinder in the building. In order of preference — (a) sealed-for-life envelope with a scheduled swap performed by a field tech, cylinder never on site; (b) refill service where the tech brings and removes the cylinder same-visit, staying under 300 cu ft and outside patient care areas; (c) if a facility insists on self-service, ship a single E-cylinder with a documented storage location pre-cleared by their facilities manager. Get NFPA 99 sign-off from facilities **before** the pilot. Assisted living and private homes are much easier than hospitals here — an argument for sequencing hospitals last.

### 🟠 4. Hospital infection control — solvable, but redesign the skin
Noncritical surfaces contacting the patient environment must be disinfectable with an **EPA-registered hospital disinfectant**, and shared equipment must be wiped between patients ([CDC](https://www.cdc.gov/infection-control/hcp/disinfection-sterilization/healthcare-equipment.html)). Typical label contact time is up to 10 minutes wet. A thin mylar envelope with seams and a fabric gondola will fail a wipe-down review: quaternary ammonium and bleach wipes degrade metallized films, seams trap soil, and nothing about it survives repeated saturation.

**Workaround:** make the *envelope* single-patient-assigned and disposable (mylar is cheap — treat it as a consumable, which also solves helium permeation), and make every hard component — gondola, camera housing, props, base station — smooth, sealed, crevice-free, and validated against the specific disinfectants the target systems use (get their actual list; it varies). Document a cleaning IFU. **Do not pitch one blimp shared between rooms.** Plan for the base station being the only thing that stays.

### 🟡 5. Facility-initiated cameras fall outside the granny-cam safe harbors ⚠️
Roughly **19 states** authorize cameras in nursing homes, with Illinois's [Authorized Electronic Monitoring in Long-Term Care Facilities Act (210 ILCS 32/)](https://law.justia.com/codes/illinois/chapter-210/act-210-ilcs-32/) treated as the model and Ohio's **Esther's Law** (2022) as the most comprehensive ([Credenza](https://credenzahealth.com/facilities/resources/which-states-allow-cameras-in-nursing-homes-overview-and-faq); [Skilled Nursing News](https://skillednursingnews.com/2026/01/a-lifeline-resurgence-in-legislation-on-electronic-monitoring-devices-in-nursing-homes/)). Federal law backstops this with a resident right to privacy in "oral, written, and electronic communications" at [42 CFR § 483.10(e)](https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-G/part-483/subpart-B/section-483.10) (F-tag F583).

**Two structural problems, both a reading of the text rather than settled law:**
1. These statutes authorize **resident-initiated** monitoring. A **facility** deploying Helpee across rooms isn't the fact pattern they bless, so the safe harbor may simply not apply.
2. Illinois defines an electronic monitoring device as a **"fixed position video camera"** or audio recorder. A blimp is by definition not fixed-position — so Helpee may fall outside the statutory safe harbor *even when a resident requests it*, landing in unlegislated space.

**Workaround:** run the **resident/family-initiated** model wherever possible — the resident or surrogate consents and requests, the facility merely permits. Follow the AEM Act's full checklist regardless of whether it strictly binds (written consent form, roommate consent, doorway signage, facility notice, no retaliation, pause-on-request); it's the closest thing to a national template and following it voluntarily is excellent optics with a facility's compliance officer. Sequence launch states by statutory clarity: **Illinois and Ohio first**, states with active hostile legislative history (Iowa has [rejected such bills six years running](https://iowacapitaldispatch.com/2026/02/05/senate-panel-rejects-bill-to-ensure-care-facility-residents-can-use-granny-cams/)) last.

### 🟡 6. IEC 60601 in the patient environment
IEC 60601-1 defines a **1.5 m** patient environment ([RAM Technologies](https://ramtechno.com/understanding-patient-spaces-in-en-60601-1/)). Non-medical equipment doesn't need full 60601-1 certification, but within that zone it must meet the applicable product standard (IEC 62368-1 for IT equipment) **and** satisfy 60601-1 **leakage-current limits**, typically handled by specifying a 60601-1-rated medical power supply.

**Workaround:** cheap if done at design time — spec a **60601-1 medical-grade power supply** for the base station now (a few dollars of BOM), and test to **IEC 60601-1-2** for EMC and **IEC 60601-1-11** for the home-healthcare environment. Retrofitting a power supply after tooling is not cheap. EMC near infusion pumps and telemetry is the specific thing a hospital's clinical engineering group will ask about, so having the 60601-1-2 report is what gets you in the door.

### 🟢 7. Latex — verified non-issue, and a small marketing win
Latex balloons are banned in many hospitals for allergy and pediatric-choking reasons, and **mylar/foil is the explicitly approved substitute** — Boston Children's welcomes mylar and bans latex hospital-wide; some hospitals hand out free mylar swaps at the door ([Boston Children's](https://www.childrenshospital.org/conditions-treatments/latex-allergy); [American Latex Allergy Association](https://latexallergyresources.org/faqs/should-latex-allergy-reduction-policies-include-banning-latex-balloon-use)). The material choice is already correct. **State "latex-free, mylar envelope" on the spec sheet** — it preempts the question and signals homework done.

### 🟢 8. Joint Commission
No Helpee-specific standard. It surfaces indirectly through the facility's Environment of Care and Information Management programs — which is to say it's the *customer's* problem, made easy by supplying the cleaning IFU, the 60601-1-2 EMC report, and the NFPA 99 helium plan as a pre-assembled packet.

---

## E. Liability & disclaimers

### What the PERS case law actually teaches
The pattern across the precedents is clear and a little counterintuitive: **defendants win on causation and lose on their own marketing.**

- **Won (directed verdict, CT):** an 88-year-old was found dead after the alert failed to transmit because her phone was off the hook. Plaintiff couldn't prove **what caused the death** or that an emergency existed at a given moment ([Hinshaw](https://www.hinshawlaw.com/newsroom-updates-Pers-Company-Prevails-at-Trial-of-Wrongful-Death-Suit.html); [Polito](https://www.politolaw.com/ct-court-rejects-wrongful-death-lawsuit-medical-alert-system-company/)).
- **Lost summary judgment (CA):** a jury could find the decedent **reasonably relied on the company's representations**, which were false because operators **were not 911-certified** and didn't respond in a manner calculated to ensure prompt attention. The surviving claim was **unfair business practices**, not product defect ([SDM Magazine](https://www.sdmmag.com/articles/102697-summary-judgement-denied-a-death-leads-to-cautionary-pers-saga)).
- Industry counsel repeatedly note that a **limitation-of-liability clause** would have changed outcomes ([SDM](https://www.sdmmag.com/articles/93960-limited-liability-clause-would-have-helped-in-wrongful-death-lawsuit)).

**The takeaway for Helpee:** marketing copy is a bigger liability driver than the miss rate. A device that promises less and delivers reliably is far safer than one that promises "never misses a fall" and delivers 95%. **This is the same constraint as §B, arriving from a completely different direction — treat marketing-claim review as a gating step on every release, not a legal afterthought.**

### Required disclaimers
Placed where they'll actually be read and **acknowledged with a logged click** at onboarding, not buried in a EULA:

1. **"Helpee is not a medical device and is not a substitute for professional medical care, supervision, or emergency services."**
2. **"Helpee does not call 911. In an emergency, call 911."** — plainly stated; it's true in v1 and it's the best liability shield.
3. **"Fall detection is not guaranteed. Helpee may miss falls or report falls that did not occur. Do not rely on Helpee as your only means of getting help."**
4. **"Notifications depend on power, Wi-Fi, and your phone. Helpee cannot notify anyone if any of these are unavailable."**
5. **"Helpee is an AI. It is not a person, a nurse, or a doctor."** — required by both AI companion laws, so it does double duty.
6. Recording notice naming what is captured, what leaves the device, and who can see it.
7. **Limitation of liability + liquidated damages** capped at fees paid, with an arbitration clause. ⚠️ **Verify with counsel:** enforceability against wrongful-death claims varies by state and some states won't enforce it for personal injury.

Pair these with **operational** safeguards, because they matter more than the words: escalation **acknowledgment tracking** with automatic fallback to the next contact tier on non-acknowledgment, a visible connectivity/battery health indicator, proactive alerts to family when the device has been offline, and a logged **quarterly re-acknowledgment** of the limitations.

### Product liability for a floating object
Low but not zero, and the mass is a red herring. The real theories are **startle-induced falls** (a blimp drifting up behind a frail person with impaired balance — the injury mechanism is the fall, and the damages are a fractured hip, not a bruise from the balloon), **entanglement** with oxygen tubing, IV lines, or a cannula, **propeller contact** with skin or hair, **ingestion or mouthing** of mylar fragments by residents with dementia, and **obstruction of egress or staff access during a code**.

**Mitigations:** fully shrouded props with finger-safe guards, a hard minimum standoff distance from detected people, no autonomous approach from behind or above, an audible movement cue so a person with low vision can localize it, immediate descent-and-land on any fault, geofenced no-fly zones around beds and medical equipment, and an accessible physical kill switch. Carry **product liability insurance** before the first unit ships, and require it in facility contracts.

---

## F. Top 5 regulatory risks, ranked

### 1. 🔴 Illinois BIPA class action — highest expected cost, cleanest fix
**Why #1:** the only item with a private right of action, statutory damages needing no proven injury, a mature plaintiffs' bar, and the home state as ground zero. A single facility deployment sweeps in residents, visitors, and staff.
**Mitigation:** architecturally forbid face recognition and speaker identification in v1. Pose/keypoint only, no persistent matchable template, ever. Document the prohibition in the architecture doc so it survives future engineers. If voice ID becomes a must-have, gate it behind § 15(b)-grade written consent with a published retention schedule.
**How you'll know it worked:** a security reviewer or opposing expert can inspect the pipeline and find no template store. A verifiable property, not a policy claim.

### 2. 🔴 AI companion law non-compliance — in scope today
**Why:** Helpee matches both definitions precisely — sustained relationship, retained memory, unprompted emotion-based questions, ongoing personal dialogue. **[NY GBL Art. 47 §§ 1700–1704](https://www.fenwick.com/insights/publications/new-yorks-ai-companion-safeguard-law-takes-effect) took effect Nov 5, 2025** (AG enforcement, up to **$15,000/day**), and **[CA SB 243](https://www.skadden.com/insights/publications/2025/10/new-california-companion-chatbot-law) took effect Jan 1, 2026** with a **private right of action** at the greater of actual damages or **$1,000 per violation** plus fees. CA exempts smart speakers *without* sustained relationship — Helpee is the opposite of that exemption. Governor Hochul [wrote directly to AI companion companies](https://www.governor.ny.gov/news/governor-hochul-pens-letter-ai-companion-companies-notifying-them-safeguard-requirements-are) notifying them the requirements were live, so ignorance isn't available.
**Mitigation:** ship §C item 5 in v1 — spoken AI disclosure, 3-hour recurring reminders, self-harm detection with 988 referral, published protocol, logged referral counts for the July 1, 2027 CA report.
**Watch item:** ⚠️ neither law was written with **embodied voice robots for cognitively impaired elders** in mind. An anthropomorphic floating companion talking to someone with dementia is the most sympathetic possible fact pattern for an AG or a legislator looking for an example. Expect scrutiny disproportionate to company size; consider being conspicuously over-compliant as a moat.

### 3. 🟠 Marketing claims creating FDA jurisdiction you didn't intend
**Why:** the most common way a wellness product becomes a device is a founder or marketer writing "monitors your parent's health" on a landing page. It costs nothing to trigger and is expensive to unwind — and per §E it simultaneously destroys the liability defense.
**Mitigation:** a written claims policy, a **single reviewer with veto** over all public copy including decks, app-store text, and social posts, the §B forbidden-terms list in CI as a lint check on marketing repos, and a quarterly sweep of live copy. Log every claim change.
**How you'll know:** you can produce, on request, every public claim ever made about Helpee with a date and an approver.

### 4. 🟠 Facility audio consent / eavesdropping exposure
**Why:** an aide or a visitor recorded without consent in Illinois or California has a personal claim. CA § 637.2 is **$5,000 per violation** with no injury needed, and a facility deployment scales the plaintiff class automatically.
**Mitigation:** the anti-surreptitious design in §D.1 — audible self-announcement, persistent visible recording indicator, doorway signage, admission-packet disclosure, no default audio retention, hardware mute with visible state, auto-pause on unenrolled voice. Launch first in **one-party-consent states** while counsel clears the all-party ones; that sequencing costs almost nothing and removes the sharpest tail risk from the riskiest early deployments.
**Reality check:** Illinois's post-*Melongo* two-element test genuinely favors an obviously-visible robot. A real path, not wishful thinking — but it needs a state-by-state memo before facility sales, not after.

### 5. 🟡 The FDA line moving under you — via scope creep, not enforcement
**Why:** v1 is defensible. The risk is v1.3, added by a well-meaning engineer: auto-911 dispatch (lands in FDA's own ILQ example), clinical urgency scoring for nurses (HCP-facing black-box CDS — the worst position available), continuous temperature (510(k) required per the June 2025 carve-out), or "detects UTI/early dementia" (dispositive disease claim). Note also that the **FTC's** [Sept 11, 2025 6(b) inquiry into AI companion products](https://www.ftc.gov/news-events/news/press-releases/2025/09/ftc-launches-inquiry-ai-chatbots-acting-companions) signals active federal interest in exactly this category, and 6(b) studies routinely precede enforcement.
**Mitigation:** write the four bright lines into the architecture doc as **product-level prohibitions requiring regulatory sign-off to cross**: (1) no autonomous emergency-services dispatch, (2) no clinical severity ranking or care recommendations to clinical staff, (3) no physiological measurement, (4) no disease-specific inference. Re-run the classification analysis at every feature gate.
**One important asterisk on "we're not a device":** the ILQ exemption is a **premarket** exemption only. If Helpee or a facility customer ever concludes the fall-alert function is an ILQ device, general controls still attach — establishment registration and device listing (21 CFR Part 807), the **QMSR** which replaced the old Quality System Regulation at 21 CFR Part 820 and aligns it with ISO 13485 (⚠️ **verify the effective date**; recollection is Feb 2, 2026 but unconfirmed), MDR adverse-event reporting (Part 803), labeling (Part 801), and UDI (Part 830). Market practice (SafelyYou, Apple, Vayyar) is that nobody in this category registers, and that's a defensible position — but **budget for a quality system as a Series-A diligence item**, because an enterprise health-system customer or a sophisticated investor will eventually ask, and "SafelyYou doesn't either" is a weaker answer in a diligence room than in a product meeting.

---

## Aviation & RF (confirmed, both low-burden)

- **FAA has no jurisdiction indoors.** Per FAA's own FAQ, Part 107 applies to operations in the National Airspace System, and [FAA confirms indoor-only operations are outside its rules](https://www.faa.gov/faq/do-faa-rules-and-regulations-apply-commercial-uas-or-drone-operations-conducted-indoors-only). Interiors are not navigable airspace. **No registration, no Remote ID, no Part 107 pilot.** The moment a unit exits a door it is in the NAS, so build a hard geofence at doors and windows, plus auto-land on egress detection — a genuine v1 safety requirement, not a paperwork one.
- **FCC:** using a pre-certified module gets the intentional-radiator certification but **not** a free pass. You remain responsible for (a) **Part 15 Subpart B** authorization of the host as an **unintentional radiator** (motors, ESCs, and camera electronics are real emitters), (b) honoring the module's integration conditions — approved antenna type/gain, output power, and co-location evaluation, (c) **RF exposure** compliance for the final configuration, and (d) displaying the **FCC ID** on the product or electronically ([Nemko on KDB 996369](https://www.nemko.com/hubfs/Radio%20-%20Testing%20Strategies%20and%20best%20practice%20for%20using%20approved%20modules%20per%20FCC%20KDB99369.pdf); [MiCOM Labs](https://micomlabs.com/fcc-ised-wireless-module-compliance/)). Budget one lab visit for Subpart B; not expensive but not zero.

---

## Sequencing recommendation

The regulatory geography points to a specific go-to-market order, cheap to follow now versus expensive to correct later:

**Private homes → assisted living → skilled nursing → hospitals.** Helium storage, IEC 60601, infection control, and EMC are hospital-grade problems that mostly evaporate in a private residence, while the consent analysis is dramatically simpler with one or two consenting adults than in a shared room with rotating staff. Within facilities, start in states with clear granny-cam statutes (Illinois, Ohio) and, if counsel wants more time on the audio question, prefer one-party-consent states for the earliest deployments.

Three things are worth doing before the first unit ships, because each is ~10x cheaper now: the **consent/audit data model** (§C.1–2), the **60601-1 medical power supply** in the base station BOM, and the **AI-disclosure + crisis protocol** (§C.5, already legally required). Everything else can follow the product.

**The single highest-leverage regulatory decision already made is "no auto-911 in v1."** It's what keeps Helpee outside FDA's own worked example of a regulated emergency-alert device. Treat it as an architectural invariant, not a roadmap item.
