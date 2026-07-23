from __future__ import annotations

from dataclasses import replace

import httpx

from pipeline.github_api import GitHubApi


def test_github_client_retries_rate_limits(monkeypatch, cfg):
    calls = 0
    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429 if calls == 1 else 200, json={"ok": True}, headers={"retry-after": "0"})
    monkeypatch.setattr("pipeline.github_api.time.sleep", lambda _seconds: None)
    client = httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler))
    api = GitHubApi(replace(cfg, request_retries=2), client=client)
    assert api.get_json("/test") == {"ok": True}
    assert calls == 2
    client.close()
