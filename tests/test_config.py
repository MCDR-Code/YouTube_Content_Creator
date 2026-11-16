"""Checks the fixed rules in config.yaml before any agent exists."""
import os

import pytest

import ycc  # noqa: F401
from ycc.config import load_settings


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.delenv("YCC_MODE", raising=False)
    return load_settings()


def test_ten_agents_each_with_its_own_prune_key(settings):
    assert len(settings.agents) == 10
    key_names = [a.key_env for a in settings.agents.values()]
    assert len(set(key_names)) == len(key_names), "two agents share a Prune key"
    assert all(k.startswith("PRUNE_KEY_") for k in key_names)


def test_models_use_prune_openai_route(settings):
    for a in settings.agents.values():
        assert a.model.startswith("openai/"), f"{a.name} model must start with openai/ to reach Prune"


def test_every_agent_has_a_spend_cap(settings):
    for a in settings.agents.values():
        assert 0 < a.daily_cap_usd <= 2.0


def test_uploads_are_private(settings):
    assert settings.privacy_status == "private"


def test_real_mode_points_at_prune(monkeypatch):
    monkeypatch.setenv("YCC_MODE", "real")
    s = load_settings()
    assert s.base_url == "https://api.withprune.com/v1"


def test_mock_mode_uses_fake_keys_and_local_prune(settings):
    assert settings.mode == "mock"
    assert settings.base_url.startswith("http://127.0.0.1")
    assert settings.prune_key("scriptwriter") == "prune_mock_scriptwriter"


def test_real_mode_rejects_non_prune_key(monkeypatch):
    monkeypatch.setenv("YCC_MODE", "real")
    monkeypatch.setenv("PRUNE_KEY_SCRIPTWRITER", "sk-openai-key")
    with pytest.raises(RuntimeError):
        load_settings().prune_key("scriptwriter")


def test_swarms_telemetry_is_off(settings):
    assert os.environ["SWARMS_TELEMETRY_ON"] == "false"


def test_direct_openai_key_is_removed(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-be-used")
    load_settings()
    assert "OPENAI_API_KEY" not in os.environ
