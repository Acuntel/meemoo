# Research 02 — Own-Stack Voice Survey (July 2026)

> Produced 2026-07-25 by the voice-stack research agent. Part of the Helpee
> pre-build research phase. See docs/RESEARCH.md for the synthesis.

**Headline:** The constitution wins on voice. As of mid-2026 the best self-hostable STT *beats* Whisper-large and the best permissively-licensed TTS *beats ElevenLabs in a blind test* — both under MIT/Apache/CC-BY. The one place hosted is still significantly better is the **LLM**, not the voice. Second headline: **the Raspberry Pi 5 cannot hold the full loop at conversational latency** (measured 8–25s round-trip with a local LLM), so the base-station decision is effectively forced up a tier.

---

## A. Recommended own-stack voice architecture

| Stage | Pick | Why | License |
|---|---|---|---|
| Wake word (on blimp) | **microWakeWord** on ESP32-S3 | 4 models concurrent on S3; ~0.1–0.19 false accepts/hour | Apache 2.0 |
| On-device AEC/AGC/NS | **XMOS XU316** (or ESP-SR AFE) | mic+speaker share one clock — see §D | HW / Apache 2.0 |
| VAD | **Silero VAD** | tiny, ubiquitous, acoustic-only | MIT |
| Turn-taking | **smart-turn v3** | semantic endpointing, 12 ms CPU | open weights + data + training script |
| STT | **Moonshine v2 Streaming** (Small 123M or Medium 245M) | Medium = 6.65% WER, beats Whisper-large-v3 (7.44%) at 1/6 the size; true streaming; no hallucination-on-silence | **MIT** |
| LLM | **Qwen/Llama 7–8B Q4 local** + frontier hosted for hard turns | see §B | varies |
| TTS | **Pocket TTS (Kyutai, 100M)** primary, **Piper** offline floor | ~200 ms first chunk, ~6× realtime on *2* CPU cores, streaming, voice cloning | CC-BY-4.0 / MIT |
| Orchestration | **Pipecat** | best local-first dev story; smart-turn + interruption handling built in | BSD |

Sources: [Moonshine](https://github.com/usefulsensors/moonshine), [Pocket TTS](https://huggingface.co/kyutai/pocket-tts), [smart-turn v3](https://www.daily.co/blog/announcing-smart-turn-v3-with-cpu-inference-in-just-12ms/), [micro-wake-word](https://github.com/OHF-Voice/micro-wake-word).

### Latency budget to first audio (user stops speaking → blimp starts talking)

Streaming everywhere: STT emits partials during speech, LLM streams into TTS at the first clause boundary, TTS streams audio chunks. So the budget counts only the *tail* after the user's last word.

| Stage | Pi 5 8GB | N100/Beelink 32GB | **Mac mini M4 24GB** | Jetson Orin Nano Super 8GB |
|---|---|---|---|---|
| WiFi blimp→base | 25 ms | 25 ms | 25 ms | 25 ms |
| STT tail (Moonshine streaming) | 250–400 ms | 150–250 ms | 100–150 ms | 80–120 ms |
| smart-turn v3 | 80–150 ms | 20–40 ms | ~15 ms | ~15 ms |
| LLM TTFT + first clause (~12 tok) | **1,400–1,800 ms** (3B @ 8.8 t/s) | 800–1,000 ms (8B @ 15 t/s) | **440–560 ms** (8B @ 38 t/s) | 300–500 ms (3B @ 20–30 t/s) |
| TTS first chunk | 100 ms (Piper) / 500–700 ms (Pocket) | 250–350 ms | **~200 ms** | 150–250 ms (Chatterbox Turbo, GPU) |
| Audio back to blimp | 25 ms | 25 ms | 25 ms | 25 ms |
| **Total, fully local** | **~1.9–3.1 s** | **~1.3–1.7 s** | **~0.8–1.0 s** ✅ | **~0.6–0.9 s** ✅ |
| **Total, hosted LLM** | ~0.9–1.4 s | ~0.7–1.0 s | ~0.6–0.8 s | ~0.5–0.7 s |

Honesty about these numbers: the per-stage figures are sourced, the **sums are estimates** — nobody publishes an end-to-end bench for this exact stack. Two caveats worth naming:

1. A community Pi-5 guide measured **15–25 s unoptimized, 8–12 s "optimized"** for a full local loop ([source](https://bmdpat.com/blog/raspberry-pi-5-local-voice-ai-2026)). The ~2–3 s figure here is much lower because it counts *first audio with clause-level streaming*, and they appear to be counting full-response generation. The delta between those two numbers is exactly what aggressive streaming buys — but it's unproven until we bench it.
2. Well-tuned Pipecat/LiveKit stacks are reported at **0.7–1.1 s voice-to-voice** in production, which brackets the Mac-mini estimate and is the best external sanity check available ([source](https://www.channel.tel/blog/pipecat-vs-livekit-voice-framework-decision)).

### The three-tier graceful-degradation design

The reason to own STT and TTS isn't cost — it's that **Helpee's voice must never change**. For an elderly user, an assistant that sounds like a different person when the internet drops is a different *entity*. Same Moonshine, same Pocket TTS voice in all three tiers:

- **Tier 0 — blimp alone (base station down):** microWakeWord + a "stop" model + a handful of canned ESP-SR MultiNet intents. Helpee still acknowledges its name and can be silenced. Never mute-dead.
- **Tier 1 — base station, no internet:** Moonshine → local 7–8B → Pocket TTS. Full conversation, same voice, slightly slower and slightly less clever.
- **Tier 2 — online:** frontier LLM for the warm/ambiguous/high-stakes turns.

---

## B. Where third-party is still significantly better — the honest gap

**TTS: self-hosted wins outright. Reject third-party.** Chatterbox Turbo (350M, **MIT**, Resemble AI) beat ElevenLabs Turbo v2.5 in a blind test **65.3% to 24.5%** — the first vendor-run blind result where open MIT weights beat ElevenLabs by a wide margin ([Resemble](https://www.resemble.ai/learn/models/chatterbox-turbo), [FindSkill](https://findskill.ai/blog/best-open-source-tts-2026/)). On a leaderboard basis ElevenLabs v3 sits at 1542 Elo vs Chatterbox Turbo 1590 ([CodeSOTA](https://www.codesota.com/guides/tts-models)). What ElevenLabs still genuinely leads: cloning depth, *multilingual* naturalness, and directorial emotion control. For a single English-speaking grandmother voice, none of those three is load-bearing for us. **The constitution's test is not met — build it.**

**STT: self-hosted wins or ties. Reject third-party.** Open weights now top the accuracy leaderboard outright (IBM Granite Speech 4.1 2B at 5.33% mean WER, ahead of cloud APIs — [CodeSOTA](https://www.codesota.com/speech-to-text)), and Moonshine Medium Streaming beats Whisper-large-v3 at 1/6 the parameters. Cloud APIs retain an edge only in managed streaming infrastructure and multilingual scale. **Not significantly better.**

**LLM: hosted is genuinely, significantly better. This is where the exception applies.** An 8B Q4 model on a Mac mini is not conversationally equal to a frontier model for what Helpee actually has to do — hold months of context about a person's life, be warm without being saccharine, handle grief and confusion, and *not* give a vulnerable 82-year-old wrong medication advice. That last one isn't a quality preference, it's a safety floor, and small local models are measurably worse at refusing confidently-wrong medical claims.

Recommendation: **hosted frontier LLM as the primary brain, local 7–8B as a first-class offline fallback, not a toy.** This satisfies the constitution on its own terms (significantly better + the self-hosted option provably underperforms on a safety-critical axis) while keeping the thing that matters most — Helpee's *voice and ears* — 100% ours. The user can never tell which brain is driving, because the voice is identical.

**Full-duplex speech-to-speech: not yet, and the reason is architectural.** Moshi (Kyutai, CC-BY-4.0) hits 160 ms theoretical / ~200 ms practical latency, but on an **L4 GPU**, and a June 2026 survey concludes end-to-end S2S models still lose access to the reasoning and planning ability that cascaded pipelines retain ([arXiv 2606.07547](https://arxiv.org/pdf/2606.07547)). For a companion that must remember and reason about a person's life, that trade is backwards. Keep the cascade; re-evaluate in ~6 months — PersonaPlex and Qwen3-Omni are moving fast.

### License traps — this filtered out most of the "best" open TTS

For a commercial product, a large share of the models people call open-source are not usable:

| Rejected | License | Note |
|---|---|---|
| XTTS-v2 | CPML | non-commercial |
| F5-TTS | CC-BY-NC 4.0 | non-commercial |
| Voxtral TTS | CC-BY-NC 4.0 | the "62.8% beats ElevenLabs Flash" model — unusable |
| Fish Audio S2 Pro | research-only | |
| Supertonic 3 | OpenRAIL-M | commercial restrictions; also sounds robotic at 2-step |

Clean for commercial use: **Piper (MIT), Kokoro (Apache 2.0), Chatterbox family (MIT), Pocket TTS (CC-BY-4.0, attribution required), Moonshine (MIT)**. Two things to verify before committing: **Parakeet TDT v3's license** — sources conflict between CC-BY-4.0 and Apache 2.0 — and note that **Chatterbox watermarks every output** with PerTh by default (arguably a feature for us, but know it's there).

---

## C. Wake-word plan, including the on-blimp ESP32 path

**Two-phase, one training pipeline.** Train on synthetic samples from [piper-sample-generator](https://github.com/rhasspy/piper-sample-generator) plus HuggingFace's pre-computed negative spectrogram sets, then emit both targets:

- **Phase 1 (dev, on base station): openWakeWord.** Custom model trainable in ~20 minutes, more accurate than Porcupine in the author's own comparison, and a single Pi 3 core runs 15–20 models concurrently — so we can A/B a dozen candidate phrasings cheaply ([openWakeWord](https://github.com/dscripka/openWakeWord)).
- **Phase 2 (production, on blimp): microWakeWord** → TFLite-Micro on ESP32-S3. Achievable **0.16 false accepts/hour on DipCo, <0.1/hr on the Picovoice benchmark**; the shipped "Hey Jarvis" model runs 0.187 FA/hr. Tune via `probability_cutoff` (higher = fewer false accepts, more misses) and `sliding_window_size` (smaller = lower latency, more false accepts), plus the optional VAD gate model ([ESPHome docs](https://esphome.io/components/micro_wake_word/)).

**Reject Porcupine.** It's proprietary, and openWakeWord already out-scored it. No exception needed.

**Budget real time for training.** The maintainers are blunt: microWakeWord is "intended for advanced users," "training a model that works well is still very difficult," and the starter notebook explicitly warns its output "will most likely not be usable." Assume 1–2 weeks of hyperparameter and sample-generation iteration, not an afternoon.

### ⚠️ Name warning — "Helpee" is a bad wake word, and specifically bad for elder care

Two independent problems:

1. **Phonetic collision.** Bare "Helpee" is two syllables and sits inside a dense neighborhood — *help, helper, happy, Halle, hello, hey P*. microWakeWord's false-accept rates are quoted for 3–4 syllable phrases like "Okay Nabu" and "Hey Jarvis"; short, common-phoneme words do materially worse.
2. **The safety-critical one.** In an elder-care product the word **"help"** will be shouted in genuine distress. A wake word that partially matches it creates failure in *both* directions: false wakes on a real emergency, and the word "help" being swallowed by wake-word logic instead of reaching intent detection.

Recommendation: ship **"Hey Helpee"** (4 syllables) as the wake word, and separately train **"help"** as its own always-on distress-intent model with a deliberately *low* threshold — treating a false alarm as cheap and a miss as expensive. These are opposite tuning goals and must not share one model.

---

## D. Echo cancellation and barge-in with speaker 10 cm from mic

**Do AEC on the blimp payload, not the base station.** This is the single most important architectural call in the audio path, and the reason is clock drift: AEC works by subtracting a *known reference* of what the speaker is playing from what the mic captured, which requires both to run on one clock. If the blimp streams mic audio over WiFi and receives TTS over WiFi, capture and playback sit in different clock domains with independent drift, and the adaptive filter spends its life chasing alignment instead of cancelling. On the payload, an I2S mic and I2S speaker share the same bit clock and the problem largely disappears.

This is exactly why Home Assistant put a **dedicated XMOS XU316** next to the ESP32-S3 in Voice PE, handling echo cancellation, stationary noise removal and auto gain control across a **dual-mic array** ([Voice PE](https://www.home-assistant.io/voice-pe/)). Copy that.

**Four defenses, layered — because no single one is sufficient during double-talk:**

1. **Hardware AEC on the payload** — XMOS XU316 (proven, but check mass/power against the blimp's lift budget) or **Espressif ESP-SR's AFE**, which bundles AEC + noise suppression + vadnet + WakeNet on the ESP32-S3 itself and costs nothing extra in parts. ESP-SR's CPU/RAM cost figures could not be retrieved — **treat the "AEC and 4 wake-word models fit simultaneously on one S3" assumption as unverified** and bench it before locking the PCB.
2. **Partial ducking, not muting.** Drop mic gain 10–20 dB during playback rather than gating it. Full mute kills barge-in, which for a companion that sometimes monologues is unacceptable ([Coval](https://www.coval.ai/blog/voice-ai-echo-cancellation/)).
3. **A dedicated on-device "stop" wake word.** Home Assistant runs three microWakeWord models at once — a VAD, "Okay Nabu", and a **"Stop" model enabled only while audio is playing**. This is the robust barge-in path precisely because it doesn't depend on AEC quality at all: even if cancellation fails during double-talk, "stop" still lands. Steal this directly.
4. **Software AEC on the base station as backstop only.** WebRTC **AEC3** is the better choice (pure C++, no platform deps, true cancellation, runs fine on ARM) over speexdsp, which is echo *attenuation* rather than cancellation. Note PulseAudio's `module-echo-cancel` has a history of breakage on Raspberry Pi OS Bullseye 32-bit.

**Physical mitigation matters as much as DSP.** Maximize speaker-to-mic distance and put the gondola structure between them; a blimp's envelope is a large compliant surface, so also expect structure-borne coupling, not just air path. 10 cm with a hard mechanical path is a harder AEC problem than 10 cm across open air.

---

## E. What to steal from Home Assistant Voice PE and ESPHome

This is the closest existing analogue to the blimp payload, it's fully open (KiCad schematics and board layout published), and it's had a hardware generation of field debugging. Steal liberally.

**Take the hardware topology wholesale:** ESP32-S3 for connectivity and wake word + **XMOS XU316** for audio front-end + **TI AIC3204 DAC** at 48 kHz + dual-mic array. $69 retail for the whole device tells you the BOM is achievable.

**Take the "three models at once" pattern:** VAD + name + "stop", with `enable_model`/`disable_model` toggled by context so "stop" only listens during playback. Cheap, and it makes barge-in independent of AEC.

**Take the physical mute switch that cuts power to the microphones.** For an always-listening device in an elderly person's bedroom, a switch whose privacy guarantee is *electrical* rather than a software promise is the difference between a product families accept and one they unplug. This is a trust affordance, not a feature.

**Learn from their optimization result:** upstreaming their voice components into ESPHome 2025.5.0 cut Voice PE's CPU load from **72% to 35%** while mixing music and announcements simultaneously, and made even the tiny ATOM Echo capable of media playback ([Voice chapter 10](https://www.home-assistant.io/blog/2025/06/25/voice-chapter-10/)). There is a lot of headroom in a naive ESP32 audio pipeline.

**⚠️ Do not build on Wyoming.** The `wyoming-satellite` project is **deprecated / end-of-life**, replaced by "Linux Voice Assistant" over the ESPHome protocol. But LVA is itself described by its own community as "**experimental and far from finished**," with dependency conflicts and hardware assumptions baked into the guides. One maintainer's summary: Wyoming was killed before its replacement matured ([discussion](https://github.com/OHF-Voice/linux-voice-assistant/discussions/219)). The lesson: **own the transport.** Wyoming's actual insight — a dumb satellite streaming audio to a smart server over a simple framed protocol — is worth 200 lines of our own code and zero dependency risk. Borrow their *component boundaries*, not their libraries.

**Use Pipecat for the base-station pipeline, not LiveKit.** Pipecat is pipeline-first with the better local-dev story (run on localhost, no Docker server required), it's the more elegant choice for a 1:1 assistant, and it ships smart-turn v3 and interruption handling as first-class citizens. LiveKit is infrastructure-first — WebRTC rooms, needs a local server instance, and shines at many concurrent conversations, which is not our shape (one blimp per home). If we later serve multiple blimps from one base station, revisit. Worth knowing: **TEN Framework** leads raw audio-pipeline performance thanks to a C++ core, if we ever become pipeline-bound rather than model-bound.

---

## F. Base-station hardware verdict

| Tier | Cost | LLM throughput | Verdict for Helpee |
|---|---|---|---|
| **Pi 5 8GB** (+26 TOPS AI HAT ~$110) | ~$80–190 | 3B @ 8.8 t/s; 1B @ 17 t/s | ❌ **Not sufficient as the only brain.** Measured 8–25 s local round-trip. Vision + STT + TTS + LLM don't co-exist: the stack alone eats 3–4 GB, and 4 GB variants are ruled out. AI HAT accelerates *vision* but does not help llama.cpp. |
| **N100 mini PC 16GB** | ~$150–250 | ~Pi 5 class CPU; local LLM "essentially out of scope" | ⚠️ Cheap, but single-channel memory and a 16 GB ceiling make it a false economy. |
| **Intel mini PC 32GB** (Beelink SER7 / Geekom IT13) | ~$500 | Mistral 7B Q4 ~18 t/s, Llama 3 8B Q4 ~15 t/s | ✅ Viable. ~1.3–1.7 s local. Good x86 fallback. |
| **Mac mini M4 24GB** | ~$900–1,100 | **Llama 3 8B Q4 @ 38 t/s** | ✅ **RECOMMENDED** |
| Mac mini M4 Pro 48GB | ~$1,900 | Llama 3.3 70B Q4 @ 9–10 t/s | Overkill; 70B at 10 t/s is too slow for voice anyway |
| **Jetson Orin Nano Super 8GB** | ~$250–400 | Gemma 2B 40–80+ t/s; 7B ~14 t/s gen / 285 t/s prefill | ✅ Best latency + only tier that runs Chatterbox Turbo locally — at the cost of CUDA/JetPack maintenance |

Sources: [PocketClaw hardware guide](https://pocketclaw.dev/guides/edge-ai-hardware-2026), [Pi 5 LLM benchmarks](https://localaimaster.com/blog/llm-raspberry-pi-5), [Jetson benchmarks](https://nexline.ai/blog/en/jetson-orin-nano-home-automation/).

### Verdict: Mac mini M4 (24 GB), ~$900

Five reasons, in order of weight:

1. **It's the only tier that clears ~1 s fully local** without a CUDA dependency — 38 t/s on 8B is 4× the Intel mini PC.
2. **Unified memory** lets vision, STT, TTS and LLM share one pool instead of fighting over 8 GB.
3. **Pocket TTS is already benchmarked at ~6× realtime on 2 CPU cores of an M4** with ~200 ms first audio — the TTS choice runs *natively fast* here and leaves the rest of the machine for vision. MLX is first-class.
4. **It's silent and sips power.** This lives in an older adult's home, likely a bedroom. A fanless-in-practice appliance is a product requirement, not a nicety — Jetson dev kits and Intel mini PCs both have audible fans under sustained load.
5. Retail availability, 5-year support, and a family member can replace it themselves.

**Take the Jetson Orin Nano Super seriously as the alternative** if the founder wants the Chatterbox-Turbo-grade voice running 100% locally (it's the only tier where the model that beat ElevenLabs actually fits — Turbo on CPU measured **44.7 s to first audio and 7.5 GB peak RAM**, which is a hard no). The trade is CUDA/JetPack maintenance burden, fan noise, and vision competing with TTS for the same 8 GB GPU.

**Where the Pi 5 does belong:** as the blimp-side or "reflex tier" compute if the payload ever outgrows the ESP32-S3 — running openWakeWord and Piper for the Tier-0 offline persona. It's a great $80 satellite. It is not the brain.

---

## Open questions that could not be closed (flagged rather than guessed)

- **ESP-SR resource budget on ESP32-S3** — can AEC + VAD + 3–4 wake-word models genuinely co-exist? Espressif's doc index didn't expose CPU/RAM figures. Bench before the PCB is locked; this determines whether we need the XMOS chip and its mass penalty.
- **Piper's real first-audio latency** — Picovoice's vendor-run benchmark says 1,510 ms FTTS on a Ryzen 7 5700X; other sources say sub-50 ms first audio on a Pi 5. These are almost certainly measuring different things (full-utterance synthesis vs streamed chunk) and Picovoice sells a competing product. Needs our own measurement.
- **Parakeet TDT v3 license** — CC-BY-4.0 or Apache 2.0? Sources conflict. Matters only if chosen over Moonshine.
- **Chatterbox-Nano (110M, MIT, 3× realtime on 8 CPU cores)** quality relative to Turbo is unpublished. If Nano retains most of Turbo's warmth *and* its voice cloning, it becomes a serious rival to Pocket TTS for the signature-voice role on the Mac mini — and it's MIT rather than CC-BY. Worth an afternoon of side-by-side listening.
- **Elderly-speech validation is non-negotiable.** Published WERs on spontaneous elderly speech: Whisper large-v3 8.6%, medium-en 9.3%, small-en 10.1% — and speakers **with dementia degrade sharply on Small models while Medium recovers most of the loss** ([CHI 2026](https://dl.acm.org/doi/10.1145/3772318.3791581), [arXiv 2604.24770](https://arxiv.org/html/2604.24770)). Two implications: **do not ship the smallest STT tier**, and no published data exists on Moonshine specifically with elderly speech — we must record our own eval set. One further point in Moonshine's favor for this population: **Whisper hallucinates phantom text during silence**, and long pauses are a defining characteristic of elderly speech. A companion that invents user utterances out of a pause is a uniquely bad failure mode here.

---

**Sources:** [Northflank STT 2026](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks) · [onResonant local STT](https://www.onresonant.com/resources/local-stt-models-2026) · [Moonshine](https://github.com/usefulsensors/moonshine) · [CodeSOTA STT](https://www.codesota.com/speech-to-text) · [CodeSOTA TTS](https://www.codesota.com/guides/tts-models) · [Picovoice on-device TTS bench](https://picovoice.ai/blog/on-device-tts/) · [Kokoro vs Supertonic CPU bench](https://heyneo.com/blog/kokoro-tts-vs-supertonic-3-tts) · [Pinggy self-hosted TTS](https://pinggy.io/blog/best_open_source_self_hosted_text_to_speech_models/) · [OpenVox local TTS](https://openvoxai.com/blog/best-free-local-tts-models-2026) · [Chatterbox](https://github.com/resemble-ai/chatterbox) · [Chatterbox Turbo](https://www.resemble.ai/learn/models/chatterbox-turbo) · [Pocket TTS](https://huggingface.co/kyutai/pocket-tts) · [micro-wake-word](https://github.com/OHF-Voice/micro-wake-word) · [ESPHome micro_wake_word](https://esphome.io/components/micro_wake_word/) · [openWakeWord](https://github.com/dscripka/openWakeWord) · [smart-turn v3](https://www.daily.co/blog/announcing-smart-turn-v3-with-cpu-inference-in-just-12ms/) · [Moshi](https://github.com/kyutai-labs/moshi) · [full-duplex survey](https://arxiv.org/pdf/2606.07547) · [on-device streaming ASR](https://arxiv.org/html/2604.14493v2) · [HA Voice PE](https://www.home-assistant.io/voice-pe/) · [HA Voice ch.10](https://www.home-assistant.io/blog/2025/06/25/voice-chapter-10/) · [Wyoming vs ESPHome](https://github.com/OHF-Voice/linux-voice-assistant/discussions/219) · [Pipecat vs LiveKit](https://www.channel.tel/blog/pipecat-vs-livekit-voice-framework-decision) · [Coval AEC](https://www.coval.ai/blog/voice-ai-echo-cancellation/) · [voice-engine/ec](https://github.com/voice-engine/ec) · [Pi 5 voice AI](https://bmdpat.com/blog/raspberry-pi-5-local-voice-ai-2026) · [Pi 5 LLM bench](https://localaimaster.com/blog/llm-raspberry-pi-5) · [edge AI hardware](https://pocketclaw.dev/guides/edge-ai-hardware-2026) · [Jetson Orin Nano](https://nexline.ai/blog/en/jetson-orin-nano-home-automation/) · [elderly ASR augmentation](https://arxiv.org/html/2604.24770) · [CHI 2026 cognitive impairment ASR](https://dl.acm.org/doi/10.1145/3772318.3791581)
