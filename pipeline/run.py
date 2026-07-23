"""Command-line orchestration for RepoScout."""
from __future__ import annotations

import argparse
import logging
from typing import Iterable

from .collectors import Collector, enabled_collectors
from .config import Config
from .enrich import enrich
from .github_api import GitHubApi
from .score import score
from .store import Store


LOG = logging.getLogger("repo_scout")


def discover(store: Store, cfg: Config, github: GitHubApi, source: str | None = None, limit: int | None = None) -> dict[str, int]:
    collectors: Iterable[Collector] = enabled_collectors(cfg)
    if source:
        collectors = [collector for collector in collectors if collector.name == source]
        if not collectors:
            raise ValueError(f"Source {source!r} is disabled or unknown")
    stats = {"discovered": 0, "errors": 0}
    for collector in collectors:
        try:
            for candidate in collector.discover(cfg, github):
                store.upsert_candidate(candidate)
                stats["discovered"] += 1
                source_key = candidate.source.split(":", 1)[1] if candidate.source.startswith("github_search:") else candidate.source
                key = f"discovered:{source_key}"
                stats[key] = stats.get(key, 0) + 1
                if limit is not None and stats["discovered"] >= limit:
                    return stats
        except Exception:
            stats["errors"] += 1
            LOG.exception("Collector %s failed", collector.name)
    return stats


def run_stage(stage: str, cfg: Config, source: str | None = None, limit: int | None = None) -> dict[str, int]:
    with Store(cfg.db_path) as store, GitHubApi(cfg) as github:
        if stage == "discover":
            return discover(store, cfg, github, source, limit)
        if stage == "enrich":
            return enrich(store, github, limit)
        if stage == "score":
            return score(store, cfg, limit)
        if stage == "export":
            return store.export_csvs(cfg.exports_dir)
        if stage == "all":
            combined: dict[str, int] = {}
            for stats in (discover(store, cfg, github, source, limit), enrich(store, github, limit), score(store, cfg, limit), store.export_csvs(cfg.exports_dir)):
                combined.update(stats)
            return combined
    raise ValueError(f"Unknown stage: {stage}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Discover and rank useful open-source repositories.")
    parser.add_argument("stage", choices=("all", "discover", "enrich", "score", "export"), nargs="?", default="all")
    parser.add_argument("--source", choices=("github_search", "hn", "reddit", "awesome"))
    parser.add_argument("--limit", type=int, help="Maximum items processed by the selected stage.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not args.verbose:
        logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        stats = run_stage(args.stage, Config.from_env(), args.source, args.limit)
    except (ValueError, OSError) as error:
        LOG.error("Fatal configuration or storage error: %s", error)
        return 2
    LOG.info("%s complete: %s", args.stage, ", ".join(f"{key}={value}" for key, value in stats.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
