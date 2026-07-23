from __future__ import annotations

import sys
import types
from dataclasses import replace

from pipeline.config import DiscoveryProfile

from pipeline.collectors.awesome import AwesomeCollector
from pipeline.collectors.github_search import GitHubSearchCollector
from pipeline.collectors.hn import HackerNewsCollector
from pipeline.collectors.reddit import RedditCollector
from pipeline.models import github_links


class FakeGitHub:
    def get_json(self, path, params):
        assert path == "/search/repositories"
        return {"items": [{"owner": {"login": "Org"}, "name": "Tool", "html_url": "https://github.com/Org/Tool", "description": "Useful"}]}

    def readme(self, owner, repo):
        return "- [tool](https://github.com/Acme/tool)\n- https://github.com/Acme/another"


def test_github_link_extraction_deduplicates_and_skips_routes():
    links = github_links("See https://github.com/Acme/Tool. and github.com/acme/tool/issues plus github.com/topics/python")
    assert links == [("Acme", "Tool")]


def test_github_search_and_awesome_collectors_parse_candidates(cfg):
    github = FakeGitHub()
    search = list(GitHubSearchCollector().discover(cfg, github))
    awesome = list(AwesomeCollector().discover(cfg, github))
    assert search[0].full_name == "org/tool"
    assert {item.full_name for item in awesome} == {"acme/tool", "acme/another"}


def test_github_search_retains_taxonomy_profile_provenance(cfg):
    profile = DiscoveryProfile("agents", "AI agents", "Agent runtimes", ("topic:ai-agent",), 250, 365, 1, 50, "updated")
    candidates = list(GitHubSearchCollector().discover(replace(cfg, discovery_profiles=(profile,)), FakeGitHub()))
    assert candidates[0].source == "github_search:agents"
    assert "Discovery profile: AI agents" in candidates[0].context_text


def test_hn_collector_parses_algolia_payload(monkeypatch, cfg):
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"hits": [{"objectID": "1", "title": "Show HN: demo", "url": "https://github.com/Acme/demo", "story_text": ""}]}
    class Client:
        def __init__(self, **_): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def get(self, *_args, **_kwargs): return Response()
    monkeypatch.setattr("pipeline.collectors.hn.httpx.Client", Client)
    candidates = list(HackerNewsCollector().discover(cfg, FakeGitHub()))
    assert candidates[0].full_name == "acme/demo"


def test_reddit_collector_parses_posts(monkeypatch, cfg):
    cfg = cfg.__class__(**{**cfg.__dict__, "reddit_client_id": "id", "reddit_client_secret": "secret"})
    post = types.SimpleNamespace(title="Project", selftext="https://github.com/Acme/reddit-tool", url="", permalink="/r/test/1")
    reddit = types.SimpleNamespace(subreddit=lambda _name: types.SimpleNamespace(hot=lambda limit: [post]))
    monkeypatch.setitem(sys.modules, "praw", types.SimpleNamespace(Reddit=lambda **_kwargs: reddit))
    candidates = list(RedditCollector().discover(cfg, FakeGitHub()))
    assert candidates[0].full_name == "acme/reddit-tool"
