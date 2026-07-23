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


def test_discovery_taxonomy_loads_editable_profiles(monkeypatch, tmp_path):
    taxonomy = tmp_path / "taxonomy.toml"
    taxonomy.write_text("""[defaults]\nmin_stars = 250\n\n[[profiles]]\nid = \"agents\"\nlabel = \"Agents\"\ndescription = \"Agent runtimes\"\ngithub_queries = [\"topic:ai-agent\"]\n""", encoding="utf-8")
    monkeypatch.setenv("DISCOVERY_TAXONOMY_PATH", str(taxonomy))
    settings = Config.from_env(tmp_path)
    assert settings.discovery_profiles[0].id == "agents"
    assert settings.discovery_profiles[0].min_stars == 250
