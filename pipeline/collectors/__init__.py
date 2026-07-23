"""Discovery collector protocol and registry."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from ..config import Config
from ..github_api import GitHubApi
from ..models import Candidate


class Collector(Protocol):
    name: str
    def discover(self, cfg: Config, github: GitHubApi) -> Iterable[Candidate]: ...


def enabled_collectors(cfg: Config) -> list[Collector]:
    from .awesome import AwesomeCollector
    from .github_search import GitHubSearchCollector
    from .hn import HackerNewsCollector
    from .reddit import RedditCollector

    available: list[Collector] = [GitHubSearchCollector(), HackerNewsCollector(), RedditCollector(), AwesomeCollector()]
    return [collector for collector in available if cfg.source_enabled[collector.name]]

