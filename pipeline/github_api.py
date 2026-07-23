"""Small resilient GitHub REST client with conditional-response caching."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
from typing import Any

import httpx

from .config import Config


class GitHubApi:
    base_url = "https://api.github.com"

    def __init__(self, cfg: Config, client: httpx.Client | None = None) -> None:
        self.cfg = cfg
        self.cache_dir = cfg.cache_dir / "github"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if cfg.github_token:
            headers["Authorization"] = f"Bearer {cfg.github_token}"
        self.client = client or httpx.Client(base_url=self.base_url, headers=headers, timeout=cfg.request_timeout, follow_redirects=True)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "GitHubApi": return self
    def __exit__(self, *_: object) -> None: self.close()

    def _cache_path(self, path: str, params: dict[str, Any] | None) -> Path:
        key = json.dumps({"path": path, "params": params or {}}, sort_keys=True).encode()
        return self.cache_dir / f"{hashlib.sha256(key).hexdigest()}.json"

    def _request(self, path: str, params: dict[str, Any] | None = None, accept: str | None = None) -> httpx.Response:
        cache_path = self._cache_path(path, params)
        cached: dict[str, Any] | None = None
        if cache_path.exists():
            try: cached = json.loads(cache_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError: pass
        headers: dict[str, str] = {"Accept": accept} if accept else {}
        if cached and cached.get("etag"):
            headers["If-None-Match"] = cached["etag"]
        for attempt in range(self.cfg.request_retries):
            response = self.client.get(path, params=params, headers=headers)
            if response.status_code == 304 and cached:
                return httpx.Response(200, request=response.request, content=cached["content"].encode(), headers={"content-type": cached.get("content_type", "application/json")})
            if response.status_code not in {403, 429}:
                response.raise_for_status()
                cache_path.write_text(json.dumps({"etag": response.headers.get("etag"), "content": response.text, "content_type": response.headers.get("content-type", "")}), encoding="utf-8")
                return response
            if attempt == self.cfg.request_retries - 1:
                response.raise_for_status()
            retry_after = response.headers.get("retry-after")
            time.sleep(min(float(retry_after) if retry_after else 2 ** attempt, 10.0))
        raise RuntimeError("unreachable")

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request(path, params).json()

    def get_text(self, path: str) -> str:
        return self._request(path, accept="application/vnd.github.raw+json").text

    def repository(self, owner: str, repo: str) -> dict[str, Any]:
        return self.get_json(f"/repos/{owner}/{repo}")

    def readme(self, owner: str, repo: str) -> str:
        return self.get_text(f"/repos/{owner}/{repo}/readme")

