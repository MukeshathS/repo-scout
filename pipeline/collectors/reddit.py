from __future__ import annotations

from collections.abc import Iterable

from ..config import Config
from ..github_api import GitHubApi
from ..models import Candidate, github_links


class RedditCollector:
    name = "reddit"

    def discover(self, cfg: Config, github: GitHubApi) -> Iterable[Candidate]:
        del github
        if not (cfg.reddit_client_id and cfg.reddit_client_secret):
            raise RuntimeError("REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are required when REDDIT_ENABLED=true")
        import praw  # Imported lazily so GitHub/HN-only runs do not require credentials.
        reddit = praw.Reddit(client_id=cfg.reddit_client_id, client_secret=cfg.reddit_client_secret, user_agent=cfg.reddit_user_agent)
        for subreddit_name in cfg.subreddits:
            for submission in reddit.subreddit(subreddit_name).hot(limit=100):
                context = "\n".join(filter(None, [submission.title, submission.selftext, submission.url]))
                source_url = f"https://www.reddit.com{submission.permalink}"
                for owner, repo in github_links(context):
                    yield Candidate.create(owner, repo, self.name, source_url, context)

