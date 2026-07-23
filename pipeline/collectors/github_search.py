from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

from ..config import Config
from ..github_api import GitHubApi
from ..models import Candidate


class GitHubSearchCollector:
    name = "github_search"

    def discover(self, cfg: Config, github: GitHubApi) -> Iterable[Candidate]:
        if cfg.discovery_profiles:
            for profile in cfg.discovery_profiles:
                for query in profile.github_queries:
                    yield from self._search(
                        cfg, github, query, profile.min_stars, profile.max_stale_days,
                        profile.pages, profile.per_page, profile.sort, f"{self.name}:{profile.id}",
                        f"Discovery profile: {profile.label}. {profile.description}",
                    )
            return
        # Backward-compatible fallback for a custom deployment without taxonomy.
        yield from self._search(
            cfg, github, cfg.github_search_query, cfg.min_stars, cfg.max_stale_days,
            cfg.github_search_pages, 100, "stars", self.name, "Legacy GitHub search profile.",
        )

    @staticmethod
    def _search(
        cfg: Config, github: GitHubApi, query_fragment: str, min_stars: int, max_stale_days: int,
        pages: int, per_page: int, sort: str, source: str, profile_context: str,
    ) -> Iterable[Candidate]:
        since = (date.today() - timedelta(days=max_stale_days)).isoformat()
        qualifiers = [query_fragment.strip()]
        if "stars:" not in query_fragment:
            qualifiers.append(f"stars:>={min_stars}")
        if "pushed:" not in query_fragment:
            qualifiers.append(f"pushed:>={since}")
        if "archived:" not in query_fragment:
            qualifiers.append("archived:false")
        query = " ".join(part for part in qualifiers if part)
        for page in range(1, pages + 1):
            payload = github.get_json("/search/repositories", {"q": query, "sort": sort, "order": "desc", "per_page": per_page, "page": page})
            for item in payload.get("items", []):
                owner = item.get("owner", {}).get("login")
                name = item.get("name")
                if owner and name:
                    context = f"{profile_context}\nQuery: {query_fragment}\n{item.get('description') or ''}".strip()
                    yield Candidate.create(owner, name, source, item.get("html_url", f"https://github.com/{owner}/{name}"), context)
            if len(payload.get("items", [])) < per_page:
                break
