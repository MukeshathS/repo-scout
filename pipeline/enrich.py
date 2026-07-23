"""GitHub metadata enrichment for locally stored candidates."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging

from .github_api import GitHubApi
from .store import Store


LOG = logging.getLogger(__name__)


def _readme_summary(readme: str, limit: int = 4000) -> str:
    return " ".join(readme.split())[:limit]


def _license_status(spdx: str | None) -> str:
    if not spdx or spdx == "NOASSERTION":
        return "unknown"
    if spdx == "other":
        return "non_osi"
    return "verified_osi"


def _profile_stats(store: Store, stats: dict[str, int], prefix: str, full_name: str) -> None:
    for profile_id in store.taxonomy_profiles(full_name):
        key = f"{prefix}:{profile_id}"
        stats[key] = stats.get(key, 0) + 1


def enrich(store: Store, github: GitHubApi, limit: int | None = None) -> dict[str, int]:
    rows = store.repos_for_enrichment()
    if limit is not None:
        rows = rows[:limit]
    stats = {"enriched": 0, "errors": 0}
    for row in rows:
        full_name = row["full_name"]
        try:
            payload = github.repository(row["owner"], row["name"])
            canonical_name = store.canonicalize_repo(
                full_name,
                payload.get("owner", {}).get("login", row["owner"]),
                payload.get("name", row["name"]),
                payload.get("html_url", row["url"]),
            )
            full_name = canonical_name
            try:
                readme = github.readme(row["owner"], row["name"])
            except Exception as error:  # A missing README should be filtered, not abort enrichment.
                LOG.info("README unavailable for %s: %s", full_name, error)
                readme = ""
            license_data = payload.get("license") or {}
            spdx = license_data.get("spdx_id")
            license_status = _license_status(spdx)
            current = store.get_repo(full_name)
            review_flags = set(json.loads(current["review_flags"] or "[]")) if current else set()
            review_flags.discard("license_unknown")
            if license_status == "unknown":
                review_flags.add("license_unknown")
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
                "license_is_osi": int(license_status == "verified_osi"),
                "license_status": license_status,
                "review_flags": sorted(review_flags),
                "language": payload.get("language") or "",
                "topics": payload.get("topics") or [],
                "readme_summary": _readme_summary(readme),
                "is_archived": int(bool(payload.get("archived"))),
                "enriched_at": datetime.now(timezone.utc).isoformat(),
            })
            store.record_star_snapshot(full_name, int(payload.get("stargazers_count") or 0))
            store.set_status(full_name, "enriched")
            stats["enriched"] += 1
            _profile_stats(store, stats, "enriched", full_name)
        except Exception:
            stats["errors"] += 1
            LOG.exception("Could not enrich %s", full_name)
    return stats
