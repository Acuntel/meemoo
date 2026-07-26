"""Keys (write-only/masked), model tiers, presets, voices, Studio extract/apply."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

RUTH_TEXT = (
    "You're checking on my mom Ruth, she takes her heart medication at 8am "
    "and 8pm, she loves gardening and talking about her grandkids, be gentle, "
    "call me first if anything seems wrong"
)


def test_keys_are_write_only_and_masked(api_client: TestClient) -> None:
    plaintext = "sk-ant-verysecret-abcd1234"
    created = api_client.post(
        "/api/v1/devices/1/keys", json={"provider": "anthropic", "key": plaintext}
    )
    assert created.status_code == 201
    assert created.json()["masked"].endswith("1234")
    assert plaintext not in json.dumps(created.json())
    listing = api_client.get("/api/v1/devices/1/keys")
    assert plaintext not in listing.text
    assert listing.json()[0]["masked"].startswith("•")
    providers = {p["name"]: p for p in api_client.get("/api/v1/providers").json()}
    assert providers["anthropic"]["configured"] is True
    assert providers["anthropic"]["source"] == "db"
    assert api_client.delete("/api/v1/devices/1/keys/anthropic").status_code == 204
    assert api_client.delete("/api/v1/devices/1/keys/anthropic").status_code == 404


def test_model_config_tiers(api_client: TestClient) -> None:
    tiers = api_client.get("/api/v1/devices/1/model-config").json()
    assert [t["tier"] for t in tiers] == ["reflex", "conversation", "reasoning"]
    assert all(t["configured"] is False for t in tiers)
    put = api_client.put(
        "/api/v1/devices/1/model-config/conversation",
        json={"provider": "ollama", "model": "llama3.2", "max_tokens": 256},
    )
    assert put.json()["configured"] is True
    tiers = {t["tier"]: t for t in api_client.get("/api/v1/devices/1/model-config").json()}
    assert tiers["conversation"]["provider"] == "ollama"
    assert tiers["reflex"]["configured"] is False
    assert (
        api_client.put(
            "/api/v1/devices/1/model-config/nope",
            json={"provider": "x", "model": "y"},
        ).status_code
        == 404
    )


def test_presets_and_voices(api_client: TestClient) -> None:
    presets = {p["role"]: p for p in api_client.get("/api/v1/presets").json()}
    assert set(presets) == {"companion", "trainer", "hospital_checkin", "tour_guide", "tutor"}
    trainer_subs = {s["key"] for s in presets["trainer"]["sub_presets"]}
    assert {"hardcore", "encouraging", "keeps_it_simple"} <= trainer_subs
    voices = {v["key"] for v in api_client.get("/api/v1/voices").json()}
    assert voices == {"elder_male", "child", "female"}


def test_voice_preview_degrades_honestly(api_client: TestClient) -> None:
    # Headless env has no TTS engine installed — 503, never a fake 200.
    response = api_client.get("/api/v1/voice/preview", params={"character": "child"})
    assert response.status_code == 503


def test_studio_extract_works_with_zero_keys(api_client: TestClient) -> None:
    body = api_client.post(
        "/api/v1/studio/extract", json={"text": RUTH_TEXT, "device_id": 1}
    ).json()
    assert body["source"] == "deterministic"
    config = body["config"]
    assert config["person_name"] == "Ruth"
    assert config["relationship"] == "mom"
    times = {r["time"] for r in config["reminders"]}
    assert times == {"08:00", "20:00"}
    assert all(r["label"] == "heart medication" for r in config["reminders"])
    assert "gardening" in config["interests"]
    assert "gentle" in config["tone"]
    assert config["escalation_note"].startswith("call me first")


def test_studio_apply_then_current_roundtrip(api_client: TestClient) -> None:
    extracted = api_client.post(
        "/api/v1/studio/extract", json={"text": RUTH_TEXT, "device_id": 1}
    ).json()
    applied = api_client.post(
        "/api/v1/studio/apply",
        json={
            "device_id": 1,
            "config": extracted["config"],
            "raw_text": RUTH_TEXT,
            "role": "companion",
            "voice": "female",
        },
    )
    assert applied.status_code == 200
    assert applied.json()["saved"] is True
    current = api_client.get("/api/v1/studio/current", params={"device_id": 1}).json()
    assert current["person_name"] == "Ruth"
    assert current["role"] == "companion"
    assert current["voice"] == "female"
    assert current["custom_context"] == RUTH_TEXT
    assert {r["time"] for r in current["reminders"]} == {"08:00", "20:00"}


def test_usage_meter_empty_shape(api_client: TestClient) -> None:
    body = api_client.get("/api/v1/devices/1/usage").json()
    assert body["series"] == []
    assert body["today"]["requests"] == 0
    assert body["estimated_monthly_usd"] == 0.0
