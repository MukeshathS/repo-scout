"""GitHub metadata enrichment for locally stored candidates."""
from __future__ import annotations

from datetime import datetime, timezone
import logging

from .github_api import GitHubApi
from .store import Store


LOG = logging.getLogger(__name__)


def _readme_summary(readme: str, limit: int = 4000) -> str:
    return " ".join(readme.split())[:limit]


def enrich(store: Store, github: GitHubApi, limit: int | None = None) -> dict[str, int]:
    rows = store.repos_for_enrichment()
    if limit is not None:
        rows = rows[:limit]
    stats = {"enriched": 0, "errors": 0}
    for row in rows:
        full_name = row["full_name"]
        try:
            payload = github.repository(row["owner"], row["name"])
            try:
                readme = github.readme(row["owner"], row["name"])
            except Exception as error:  # A missing README should be filtered, not abort enrichment.
                LOG.info("README unavailable for %s: %s", full_name, error)
                readme = ""
            license_data = payload.get("license") or {}
            spdx = license_data.get("spdx_id")
            store.update_repo(full_name, {
                "owner": payload.get("owner", {}).get("login", row["owner"]),
                "name": payload.get("name", row["name"]),
                "url": payload.get("html_url", row["url"]),
                "description": payload.get("description") or "",
                "homepage": payload.get("homepage") or "",
                "stars": int(payload.get("stargazers_count") or 0),
                "forks": int(payload.get("forks_count") or 0),
                "open_issues": int(payload.get("open_issues_count") or 0),
                "pushed_at": payload.get("pushed_at"),
                "created_at": payload.get("created_at"),
                "license": spdx or license_data.get("name") or "",
                "license_is_osi": int(bool(spdx and spdx not in {"NOASSERTION", "other"})),
                "language": payload.get("language") or "",
                "topics": payload.get("topics") or [],
                "readme_summary": _readme_summary(readme),
                "is_archived": int(bool(payload.get("archived"))),
                "enriched_at": datetime.now(timezone.utc).isoformat(),
            })
            store.record_star_snapshot(full_name, int(payload.get("stargazers_count") or 0))
            store.set_status(full_name, "enriched")
            stats["enriched"] += 1
        except Exception:
            stats["errors"] += 1
            LOG.exception("Could not enrich %s", full_name)
    return stats
