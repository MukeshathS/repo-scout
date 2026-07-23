"""Deterministic hard filters, scoring, and automatic approval."""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

from .config import Config
from .store import Store


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def filter_reasons(repo: Any, cfg: Config, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []
    if int(repo["stars"] or 0) < cfg.min_stars: reasons.append("stars_below_minimum")
    pushed_at = _parse_datetime(repo["pushed_at"])
    if not pushed_at or (now - pushed_at).days > cfg.max_stale_days: reasons.append("stale_or_missing_activity")
    if not bool(repo["license_is_osi"]): reasons.append("missing_or_non_osi_license")
    if bool(repo["is_archived"]): reasons.append("archived")
    if not (repo["readme_summary"] or "").strip(): reasons.append("empty_readme")
    return reasons


def score_repo(repo: Any, velocity: int, cfg: Config, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    stars = max(1, int(repo["stars"] or 0))
    pushed_at = _parse_datetime(repo["pushed_at"])
    age_days = (now - pushed_at).days if pushed_at else cfg.max_stale_days
    recency = max(0.0, 1.0 - (age_days / cfg.max_stale_days))
    # Velocity is zero until two daily snapshots exist; cap keeps one outlier from dominating.
    momentum = min(1.0, math.log10(velocity + 1) / 3.0)
    return round(cfg.weight_stars * math.log10(stars) + cfg.weight_momentum * momentum + cfg.weight_recency * recency, 4)


def score(store: Store, cfg: Config, limit: int | None = None) -> dict[str, int]:
    # Include previous score rejections so a configuration adjustment can recover them.
    rows = store.repos_for_status(("enriched", "scored", "approved", "rejected"))
    if limit is not None: rows = rows[:limit]
    mirrors = set(store.find_probable_mirrors())
    stats = {"scored": 0, "approved": 0, "rejected": 0, "mirrors": len(mirrors)}
    for repo in rows:
        reasons = filter_reasons(repo, cfg)
        if reasons:
            store.reject(repo["full_name"], "score", reasons)
            stats["rejected"] += 1
            continue
        value = score_repo(repo, store.star_velocity(repo["full_name"]), cfg)
        approved = value >= cfg.auto_approve_score
        store.set_score_outcome(repo["full_name"], value, approved)
        stats["scored"] += 1
        stats["approved"] += int(approved)
    return stats
