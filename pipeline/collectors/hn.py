from __future__ import annotations

from collections.abc import Iterable

import httpx

from ..config import Config
from ..github_api import GitHubApi
from ..models import Candidate, github_links


class HackerNewsCollector:
    name = "hn"

    def discover(self, cfg: Config, github: GitHubApi) -> Iterable[Candidate]:
        del github
        params = {"query": "github.com", "tags": "show_hn", "numericFilters": f"points>{cfg.hn_min_points}", "hitsPerPage": 100}
        with httpx.Client(timeout=cfg.request_timeout) as client:
            response = client.get("https://hn.algolia.com/api/v1/search_by_date", params=params)
            response.raise_for_status()
            for hit in response.json().get("hits", []):
                context = "\n".join(filter(None, [hit.get("title"), hit.get("story_text"), hit.get("comment_text")]))
                url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
                for owner, repo in github_links("\n".join([url, context])):
                    yield Candidate.create(owner, repo, self.name, url, context)

