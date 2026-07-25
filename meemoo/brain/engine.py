"""ConversationBrain — the glue the voice pipeline calls (MASTER_PROMPT §3).

Reply flow, safety-first and fixed:
1. deterministic medical rail (no model in this path — Art. IV §4);
2. tier routing (task type → reflex/conversation/reasoning → provider+model);
3. provider call with the assembled persona system prompt — hosted or local,
   the SAME prompt, so the voice is identical in both modes (Art. III §3);
4. refusal / provider failure → deterministic warm line or scripted fallback;
5. usage row → cost meter.

The engine is a plain callable ``(text) -> str`` so it drops into
``VoicePipeline(brain=...)`` unchanged. Escalation is NEVER decided here —
that is the guardian's deterministic state machine (Art. IV).
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from meemoo.brain.medical import MEDICAL_HANDOFF, MedicalDetector
from meemoo.brain.memory import facts_for_prompt
from meemoo.brain.paraphrase import ParaphraseBank
from meemoo.brain.personality import (
    DeviceContext,
    assemble_system_prompt,
    register_prompt_version,
)
from meemoo.brain.presets import Preset, load_presets
from meemoo.brain.providers import create_provider
from meemoo.brain.router import Route, TierRouter
from meemoo.brain.scripted import ScriptedCheckin
from meemoo.brain.types import Provider, ProviderError
from meemoo.brain.usage import record_usage
from meemoo.core.versioning import set_version

logger = logging.getLogger(__name__)

ROLLING_CONTEXT_MAX = 40

#: Deterministic line when a hosted model declines (stop_reason "refusal").
REFUSAL_LINE = (
    "I'm not able to talk about that one, but I'm still right here with you. "
    "What else is on your mind?"
)


class ConversationBrain:
    """Model-agnostic conversation engine with scripted fallback."""

    def __init__(
        self,
        *,
        device_id: int = 1,
        db_factory: sessionmaker[DbSession] | None = None,
        device: DeviceContext | None = None,
        person_id: int | None = None,
        role: str = "companion",
        sub_preset: str | None = None,
        custom_context: str = "",
        router: TierRouter | None = None,
        bank: ParaphraseBank | None = None,
        provider_overrides: dict[str, Provider] | None = None,
        force_provider: str | None = None,
        force_model: str | None = None,
    ) -> None:
        self._device_id = device_id
        self._db_factory = db_factory
        self.device = device or DeviceContext()
        self._person_id = person_id
        self._custom_context = custom_context
        self._router = router or TierRouter(db_factory)
        self.bank = bank or ParaphraseBank()
        self._overrides = provider_overrides or {}
        self._force_provider = force_provider
        self._force_model = force_model
        self._presets = load_presets()
        self._preset: Preset | None = self._presets.get(role)
        self._sub_preset = sub_preset
        self._scripted: ScriptedCheckin | None = None
        self.context: list[dict[str, str]] = []
        register_prompt_version()

    # -------------------------------------------------------------- persona
    def set_preset(self, role: str, sub_preset: str | None = None) -> None:
        """Preset switch (nice-trainer → hardcore-trainer) — new persona now."""
        self._preset = self._presets.get(role)
        self._sub_preset = sub_preset
        if self._preset is None:
            logger.warning("unknown role preset", extra={"fields": {"role": role}})

    def system_prompt(self) -> str:
        facts: list[tuple[str, str, str]] = []
        if self._db_factory is not None and self._person_id is not None:
            facts = facts_for_prompt(self._db_factory, self._person_id)
        return assemble_system_prompt(
            preset=self._preset,
            sub_preset=self._sub_preset,
            custom_context=self._custom_context,
            device=self.device,
            facts=facts,
        )

    # --------------------------------------------------------------- replies
    def __call__(self, text: str) -> str:
        return self.reply(text)

    def reply(self, text: str, task_type: str = "chat") -> str:
        # 1. Medical rail — deterministic, before any model (Art. IV §4).
        if MedicalDetector().check(text) is not None:
            logger.info("medical rail fired — template handoff, no model call")
            return self._remember(text, MEDICAL_HANDOFF)

        route = self._route(task_type)
        provider = self._provider_for(route)
        if provider is None:
            return self._remember(text, self._scripted_reply(text))

        self.context.append({"role": "user", "content": text})
        del self.context[:-ROLLING_CONTEXT_MAX]
        try:
            response = provider.complete(
                self.context, route.model, route.max_tokens,
                system=self.system_prompt(),
            )
        except ProviderError as exc:
            logger.warning(
                "provider failed — scripted fallback",
                extra={"fields": {"provider": route.provider, "reason": exc.reason}},
            )
            self.context.pop()  # scripted path re-appends via _remember
            return self._remember(text, self._scripted_reply(text))

        set_version("model", f"{response.provider}:{response.model}")
        record_usage(
            self._db_factory, device_id=self._device_id,
            provider=response.provider, model=response.model, tier=route.tier,
            input_tokens=response.input_tokens, output_tokens=response.output_tokens,
        )
        reply = REFUSAL_LINE if response.refused or not response.text else response.text
        self.context.append({"role": "assistant", "content": reply})
        del self.context[:-ROLLING_CONTEXT_MAX]
        return reply

    # --------------------------------------------------------------- helpers
    def _route(self, task_type: str) -> Route:
        route = self._router.route(task_type, self._device_id)
        if self._force_provider:
            route = Route(
                provider=self._force_provider,
                model=self._force_model or route.model,
                max_tokens=route.max_tokens, tier=route.tier,
            )
        return route

    def _provider_for(self, route: Route) -> Provider | None:
        if route.provider in ("scripted", "none"):
            return None  # explicit zero-key mode — the scripted tree drives
        if route.provider in self._overrides:
            return self._overrides[route.provider]
        return create_provider(
            route.provider, device_id=self._device_id, db_factory=self._db_factory
        )

    def _scripted_reply(self, text: str) -> str:
        if self._scripted is None:
            self._scripted = ScriptedCheckin(
                name=self.device.person_name,
                reminders=list(self.device.reminders),
                bank=self.bank,
            )
        return self._scripted.reply(text)

    def _remember(self, user_text: str, reply: str) -> str:
        self.context.append({"role": "user", "content": user_text})
        self.context.append({"role": "assistant", "content": reply})
        del self.context[:-ROLLING_CONTEXT_MAX]
        return reply
