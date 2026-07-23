from __future__ import annotations

from pipeline.config import Config


def test_environment_configuration_overrides_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("MIN_STARS", "5000")
    monkeypatch.setenv("REDDIT_ENABLED", "true")
    monkeypatch.setenv("SUBREDDITS", "opensource,python")
    settings = Config.from_env(tmp_path)
    assert settings.min_stars == 5000
    assert settings.reddit_enabled is True
    assert settings.subreddits == ("opensource", "python")
