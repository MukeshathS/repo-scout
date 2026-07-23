"""Environment-backed runtime settings."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
import tomllib

from dotenv import load_dotenv


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def _csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    return default if not value else tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class DiscoveryProfile:
    """An independently tunable GitHub discovery niche."""
    id: str
    label: str
    description: str
    github_queries: tuple[str, ...]
    min_stars: int
    max_stale_days: int
    pages: int
    per_page: int
    sort: str


def _load_discovery_profiles(path: Path) -> tuple[DiscoveryProfile, ...]:
    """Load editable discovery profiles; a missing file preserves legacy search."""
    if not path.exists():
        return ()
    with path.open("rb") as handle:
        document = tomllib.load(handle)
    defaults = document.get("defaults", {})
    profiles: list[DiscoveryProfile] = []
    seen: set[str] = set()
    for item in document.get("profiles", []):
        if not item.get("enabled", True):
            continue
        profile_id = str(item["id"])
        if profile_id in seen:
            raise ValueError(f"Duplicate discovery profile: {profile_id}")
        queries = tuple(str(query).strip() for query in item.get("github_queries", []) if str(query).strip())
        if not queries:
            raise ValueError(f"Discovery profile {profile_id!r} has no github_queries")
        seen.add(profile_id)
        profiles.append(DiscoveryProfile(
            id=profile_id,
            label=str(item.get("label", profile_id)),
            description=str(item.get("description", "")),
            github_queries=queries,
            min_stars=int(item.get("min_stars", defaults.get("min_stars", 250))),
            max_stale_days=int(item.get("max_stale_days", defaults.get("max_stale_days", 365))),
            pages=int(item.get("pages", defaults.get("pages", 1))),
            per_page=int(item.get("per_page", defaults.get("per_page", 50))),
            sort=str(item.get("sort", defaults.get("sort", "updated"))),
        ))
    return tuple(profiles)


@dataclass(frozen=True)
class Config:
    root: Path
    db_path: Path
    cache_dir: Path
    exports_dir: Path
    github_token: str | None
    min_stars: int
    max_stale_days: int
    auto_approve_score: float
    github_search_enabled: bool
    hn_enabled: bool
    reddit_enabled: bool
    awesome_enabled: bool
    github_search_query: str
    github_search_pages: int
    discovery_taxonomy_path: Path
    discovery_profiles: tuple[DiscoveryProfile, ...]
    hn_min_points: int
    subreddits: tuple[str, ...]
    awesome_lists: tuple[str, ...]
    weight_stars: float
    weight_momentum: float
    weight_recency: float
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str = "repo-scout/1.0"
    request_timeout: float = 20.0
    request_retries: int = 3

    @property
    def source_enabled(self) -> dict[str, bool]:
        return {
            "github_search": self.github_search_enabled,
            "hn": self.hn_enabled,
            "reddit": self.reddit_enabled,
            "awesome": self.awesome_enabled,
        }

    @classmethod
    def from_env(cls, root: Path | None = None) -> "Config":
        root = root or Path(__file__).resolve().parent.parent
        load_dotenv(root / ".env")
        data_dir = root / "data"
        taxonomy_path = Path(os.getenv("DISCOVERY_TAXONOMY_PATH", root / "config" / "discovery_taxonomy.toml"))
        if not taxonomy_path.is_absolute():
            taxonomy_path = root / taxonomy_path
        return cls(
            root=root,
            db_path=Path(os.getenv("DB_PATH", data_dir / "repo_scout.sqlite3")),
            cache_dir=Path(os.getenv("CACHE_DIR", data_dir / "cache")),
            exports_dir=Path(os.getenv("EXPORTS_DIR", root / "exports")),
            github_token=os.getenv("GITHUB_TOKEN") or None,
            min_stars=int(os.getenv("MIN_STARS", "1000")),
            max_stale_days=int(os.getenv("MAX_STALE_DAYS", "90")),
            auto_approve_score=float(os.getenv("AUTO_APPROVE_SCORE", "4.0")),
            github_search_enabled=_bool("GITHUB_SEARCH_ENABLED", True),
            hn_enabled=_bool("HN_ENABLED", True),
            reddit_enabled=_bool("REDDIT_ENABLED", True),
            awesome_enabled=_bool("AWESOME_ENABLED", True),
            github_search_query=os.getenv("GITHUB_SEARCH_QUERY", "stars:>=1000"),
            github_search_pages=int(os.getenv("GITHUB_SEARCH_PAGES", "2")),
            discovery_taxonomy_path=taxonomy_path,
            discovery_profiles=_load_discovery_profiles(taxonomy_path),
            hn_min_points=int(os.getenv("HN_MIN_POINTS", "50")),
            subreddits=_csv("SUBREDDITS", ("selfhosted", "opensource", "coolgithubprojects", "LocalLLaMA", "SideProject", "DataHoarder")),
            awesome_lists=_csv("AWESOME_LISTS", ("sindresorhus/awesome",)),
            weight_stars=float(os.getenv("WEIGHT_STARS", "1.0")),
            weight_momentum=float(os.getenv("WEIGHT_MOMENTUM", "1.5")),
            weight_recency=float(os.getenv("WEIGHT_RECENCY", "1.0")),
            reddit_client_id=os.getenv("REDDIT_CLIENT_ID") or None,
            reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET") or None,
            reddit_user_agent=os.getenv("REDDIT_USER_AGENT", "repo-scout/1.0"),
            request_timeout=float(os.getenv("REQUEST_TIMEOUT", "20")),
            request_retries=int(os.getenv("REQUEST_RETRIES", "3")),
        )
