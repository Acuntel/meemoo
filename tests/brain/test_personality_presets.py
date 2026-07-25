"""Preset library + personality assembly."""

from __future__ import annotations

from meemoo.brain.personality import (
    PROMPT_VERSION,
    DeviceContext,
    assemble_system_prompt,
    register_prompt_version,
)
from meemoo.brain.presets import load_presets
from meemoo.core.versioning import get_versions, reset_versions

REQUIRED_ROLES = {"companion", "trainer", "hospital_checkin", "tour_guide", "tutor"}


def test_all_five_roles_load_versioned() -> None:
    presets = load_presets()
    assert set(presets) >= REQUIRED_ROLES
    for preset in presets.values():
        assert preset.version >= 1
        assert preset.sub_presets, preset.role
        assert preset.default_sub in preset.sub_presets
        assert preset.stamp.endswith(f"v{preset.version}")


def test_trainer_has_the_three_spec_sub_presets() -> None:
    trainer = load_presets()["trainer"]
    assert {"hardcore", "encouraging", "keeps_it_simple"} <= set(trainer.sub_presets)


def test_resolve_combines_role_and_personality() -> None:
    trainer = load_presets()["trainer"]
    hardcore = trainer.resolve("hardcore")
    encouraging = trainer.resolve("encouraging")
    assert "personal trainer" in hardcore.lower()
    assert hardcore != encouraging  # tone visibly changes with the sub-preset
    assert trainer.resolve("nope") == trainer.resolve(None)  # unknown → default


def test_assembly_layers_all_context() -> None:
    device = DeviceContext(
        person_name="Ruth", mode="facility", activity_mode="trainer",
        room="day room", reminders=["heart medication at 8am"],
    )
    prompt = assemble_system_prompt(
        preset=load_presets()["trainer"],
        sub_preset="hardcore",
        custom_context="Ruth loves gardening and her grandkids.",
        device=device,
        facts=[("preference", "favorite flower", "roses")],
    )
    assert "Ruth" in prompt
    assert "personal trainer" in prompt.lower()
    assert "gardening" in prompt  # owner custom context
    assert "care facility" in prompt and "day room" in prompt
    assert "heart medication at 8am" in prompt
    assert "roses" in prompt  # structured memory fact
    # base voice rules always present
    assert "one to three sentences" in prompt
    assert "never give medical advice" in prompt.lower()


def test_preset_switch_changes_prompt_visibly() -> None:
    device = DeviceContext(person_name="Ruth")
    trainer = load_presets()["trainer"]
    nice = assemble_system_prompt(preset=trainer, sub_preset="encouraging", device=device)
    hard = assemble_system_prompt(preset=trainer, sub_preset="hardcore", device=device)
    assert nice != hard
    assert "supportive" in nice.lower() or "praise" in nice.lower()
    assert "drill" in hard.lower() or "punchy" in hard.lower()


def test_prompt_version_registered_for_escalation_records() -> None:
    reset_versions()
    register_prompt_version()
    assert get_versions()["prompt"] == PROMPT_VERSION
    reset_versions()
