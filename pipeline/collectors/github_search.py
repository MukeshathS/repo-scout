from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

from ..config import Config
from ..github_api import GitHubApi
from ..models import Candidate


class GitHubSearchCollector:
    name = "github_search"

    def discover(self, cfg: Config, github: GitHubApi) -> Iterable[Candidate]:
        since = (date.today() - timedelta(days=cfg.max_stale_days)).isoformat()
        query = f"{cfg.github_search_query} pushed:>={since}"
        for page in range(1, cfg.github_search_pages + 1):
            payload = github.get_json("/search/repositories", {"q": query, "sort": "stars", "order": "desc", "per_page": 100, "page": page})
            for item in payload.get("items", []):
                owner = item.get("owner", {}).get("login")
                name = item.get("name")
                if owner and name:
                    yield Candidate.create(owner, name, self.name, item.get("html_url", f"https://github.com/{owner}/{name}"), item.get("description") or "")
            if len(payload.get("items", [])) < 100:
                break

