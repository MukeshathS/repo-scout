# RepoScout — Design

**Status:** Taxonomy-first deterministic v1; quality refinement implemented · **Date:** 2026-07-23

## Overview

RepoScout is a local, deterministic discovery pipeline for AI-agent and operator-tooling
repositories. It deliberately searches several product niches rather than treating GitHub’s most
starred repositories as a proxy for relevance.

```
taxonomy profiles ─┐
HN / Reddit / awesome ─┼─> discover + provenance -> enrich -> screen/score -> SQLite -> CSV
                       └─> GitHub Search API
```

LLM classification is a later additive stage. It does not participate in this version’s discovery,
facts, or exports.

## Discovery taxonomy

`config/discovery_taxonomy.toml` is the discovery contract. It uses TOML so the operator can add
verticals without a code change.

```toml
[defaults]
min_stars = 250
max_stale_days = 365
pages = 1
per_page = 50
sort = "updated"

[[profiles]]
id = "agent_frameworks"
label = "AI agent frameworks"
description = "General-purpose single- and multi-agent runtimes."
github_queries = ["topic:ai-agent", "\"agent framework\""]
```

The GitHub collector expands every `github_queries` entry with profile retrieval constraints and
records candidates as `source="github_search:<profile_id>"`. A repository found by several
profiles retains every source row. The initial taxonomy is intentionally broad enough to cover
agent frameworks, MCP/tools, reliability, automation, LLM interfaces, retrieval, multimodal AI,
self-hosted operator tools, and finance agents.

## Pipeline components

- **Collectors:** GitHub Search is taxonomy-driven; HN extracts GitHub links from high-signal Show
  HN posts; Reddit is optional PRAW-based link discovery; awesome lists are fetched via GitHub’s
  README API. GitHub Trending scraping is not used.
- **GitHub client:** authenticated REST, ETag cache, conditional requests, redirect following, and
  bounded 403/429 retry.
- **Enrichment:** writes GitHub facts plus a README summary and one star snapshot. It prioritizes
  rows without `enriched_at` so interrupted runs resume forward progress.
- **Screening and scoring:** taxonomy retrieval settings admit a broad candidate pool. Approval is
  a separate score decision. `license_status` (`verified_osi`, `unknown`, `non_osi`) ensures
  GitHub `NOASSERTION` is reviewable rather than treated as a confirmed rejection.
- **Store/export:** SQLite is the source of truth. `master_repos.csv` is the full audit/review
  output; `content_candidates.csv` is the top approved, unexported batch; `rejects.csv` records
  every failure reason.

## Data and state refinement

The existing `repos`, `sources`, `star_snapshots`, `rejections`, and reserved `classification`
tables remain. The additive migration adds:

- `canonical_full_name` redirect handling: update a redirected GitHub `full_name` without losing
  sources, snapshots, score, or status.
- `license_status` and a non-terminal review flag so metadata gaps remain visible in master output.
- Per-profile run counts for discovered, enriched, approved, and rejected candidates, aggregated
  from taxonomy provenance and reported by the CLI.

Lifecycle remains `discovered → enriched → scored → approved → exported`; only definitive failures
become `rejected`. Scoring configuration may move a score-rejected row back to `scored` or
`approved` on rerun.

## Runtime configuration

`.env` contains credentials, source toggles, global scoring thresholds, and an optional
`DISCOVERY_TAXONOMY_PATH`. The taxonomy has independent retrieval thresholds; global quality and
approval settings are calibrated separately. This prevents a broad query from silently becoming a
broad content-export rule.

## Testing strategy

- Unit-test TOML loading, duplicate/invalid profiles, profile provenance, and query construction.
- Record fixtures for collector parsing; no live calls in tests.
- Test redirect merges, 30-day velocity, unknown licence handling, score recovery, and export
selection.
- Run a small live profile smoke test separately from the full scheduled collection.
