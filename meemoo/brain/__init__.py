"""Meemoo brain: model-agnostic intelligence + presets (build step 04).

Layout — one concern per module, providers one-per-file:

- ``types``        provider interface (``complete``/``stream``) + response
- ``providers/``   anthropic · openai · google · ollama · fake (the 5th-file
                   proof); factory resolves creds and never crashes
- ``router``       task type → reflex/conversation/reasoning → provider+model
- ``usage``        per-request + daily token/cost rows → the cost meter
- ``personality``  base template + preset + owner context + memory facts
- ``presets/``     versioned YAML role/personality library (Setup Studio)
- ``paraphrase``   anti-repetition bank + continuity lines (+ metric)
- ``medical``      deterministic refusal-and-handoff rail (no model)
- ``scripted``     no-API-key check-in dialogue tree (always works)
- ``memory``       post-conversation fact extraction + mood note
- ``engine``       ConversationBrain — the callable the voice pipeline uses
"""
