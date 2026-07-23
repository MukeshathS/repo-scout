from __future__ import annotations

from pipeline.models import Candidate
from pipeline.run import run_stage


def test_all_stage_is_idempotent_with_mocked_api(monkeypatch, cfg):
    class Collector:
        name = "github_search"
        def discover(self, _cfg, _github):
            yield Candidate.create("Acme", "Tool", "github_search", "https://github.com/Acme/Tool", "demo")
    class FakeGitHub:
        def __init__(self, _cfg): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def repository(self, _owner, _repo):
            return {"owner": {"login": "Acme"}, "name": "Tool", "html_url": "https://github.com/Acme/Tool", "description": "demo", "homepage": "", "stargazers_count": 10_000, "forks_count": 2, "open_issues_count": 1, "pushed_at": "2026-07-22T00:00:00Z", "created_at": "2020-01-01T00:00:00Z", "license": {"spdx_id": "MIT"}, "language": "Python", "topics": ["demo"], "archived": False}
        def readme(self, _owner, _repo): return "# Tool\nUseful readme"
    monkeypatch.setattr("pipeline.run.enabled_collectors", lambda _cfg: [Collector()])
    monkeypatch.setattr("pipeline.run.GitHubApi", FakeGitHub)
    first = run_stage("all", cfg)
    second = run_stage("all", cfg)
    assert first["content_candidates"] == 1
    assert second["content_candidates"] == 0
    assert (cfg.exports_dir / "rejects.csv").exists()
