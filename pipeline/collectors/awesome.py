from __future__ import annotations

from collections.abc import Iterable

from ..config import Config
from ..github_api import GitHubApi
from ..models import Candidate, github_links


class AwesomeCollector:
    name = "awesome"

    def discover(self, cfg: Config, github: GitHubApi) -> Iterable[Candidate]:
        for full_name in cfg.awesome_lists:
            try:
                owner, repo = full_name.split("/", 1)
            except ValueError as error:
                raise ValueError(f"Invalid awesome list name: {full_name}") from error
            source_url = f"https://github.com/{owner}/{repo}"
            readme = github.readme(owner, repo)
            for candidate_owner, candidate_repo in github_links(readme):
                if f"{candidate_owner}/{candidate_repo}".lower() != full_name.lower():
                    yield Candidate.create(candidate_owner, candidate_repo, self.name, source_url, f"Listed in {full_name}")
