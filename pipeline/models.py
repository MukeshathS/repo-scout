"""Shared pipeline data structures and canonicalization helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re


GITHUB_LINK_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9][A-Za-z0-9_.-]*)/([A-Za-z0-9][A-Za-z0-9_.-]*)(?:[/?#][^\s<)]*)?",
    re.IGNORECASE,
)


def canonical_full_name(owner: str, repo: str) -> str:
    return f"{owner.strip()}/{repo.strip().removesuffix('.git')}".lower()


def github_links(text: str) -> list[tuple[str, str]]:
    """Extract unique owner/repo pairs, excluding GitHub non-repository routes."""
    ignored = {"topics", "search", "trending", "features", "login", "settings", "organizations"}
    trailing = ".,:;!')]}'\""
    found: dict[str, tuple[str, str]] = {}
    for owner, repo in GITHUB_LINK_RE.findall(text or ""):
        if owner.lower() in ignored:
            continue
        clean_repo = repo.rstrip(trailing)
        key = canonical_full_name(owner, clean_repo)
        found.setdefault(key, (owner, clean_repo))
    return list(found.values())


@dataclass(frozen=True)
class Candidate:
    owner: str
    repo: str
    source: str
    source_url: str
    context_text: str
    discovered_at: datetime

    @property
    def full_name(self) -> str:
        return canonical_full_name(self.owner, self.repo)

    @classmethod
    def create(cls, owner: str, repo: str, source: str, source_url: str, context_text: str = "") -> "Candidate":
        return cls(owner, repo, source, source_url, context_text, datetime.now(timezone.utc))
