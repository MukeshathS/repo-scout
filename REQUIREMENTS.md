# RepoScout — Requirements

**Status:** Taxonomy-first deterministic v1; quality-calibration changes planned · **Date:** 2026-07-23

RepoScout is a local research pipeline for open-source tools in the **AI-agent ecosystem**:
agent runtimes, agent-enabling tooling, AI applications, and high-utility self-hosted operator
tools. It discovers, verifies, ranks, and exports candidates; posting and content generation are
out of scope.

## Goal

Surface practical repositories with a clear user job, a credible paid-tool or workflow replacement
story, and current source-verified metadata. The target is not only repositories labelled “AI”;
it also includes privacy, local-first, document, automation, and infrastructure tools that make
AI-agent operators more capable.

## Functional requirements

### Discovery

- **FR-1** Collect candidates from GitHub Search, Hacker News (Algolia), Reddit, and curated
  awesome lists using documented APIs only.
- **FR-2** GitHub Search shall be driven by `config/discovery_taxonomy.toml`, not a hard-coded
  repository seed list. A profile has an ID, label, description, and editable GitHub query
  fragments; profiles may be added, disabled, or expanded without Python changes.
- **FR-3** The initial taxonomy shall cover: agent frameworks; MCP/protocols/tools; agent
  reliability; agent automation; LLM interfaces; knowledge/retrieval; multimodal AI;
  self-hosted operator tools; and finance agents.
- **FR-4** A candidate shall be normalized to `{owner, repo, source, source_url, context_text,
  discovered_at}`. GitHub taxonomy provenance shall retain the profile ID as
  `github_search:<profile_id>`.
- **FR-5** Each source and the GitHub collector may be run independently.
- **FR-6** Preserve all provenance for a canonical repository, including every discovery profile
  and external source that found it.

### Enrichment and screening

- **FR-7** Enrich each canonical candidate from the GitHub API with stars, forks, open issues,
  activity/creation dates, licence metadata, language, topics, description, archived state, and a
  README excerpt. Follow redirects and persist the canonical GitHub name.
- **FR-8** Record daily star snapshots and compute 30-day velocity only when a 30-day baseline is
  available.
- **FR-9** Enrichment must be resumable, idempotent, and progress never reset after interruption.
- **FR-10** Separate **retrieval** from **approval**. A taxonomy profile may use broad discovery
  settings (initially 250 stars and 365 days) while approval remains score-based. Candidates that
  miss an approval threshold stay auditable in `master_repos.csv` rather than disappearing.
- **FR-11** Reject only definitive failures (archived, empty README, or confirmed unsuitable
  licence). GitHub `NOASSERTION`/missing SPDX data must be represented as `license_unknown` for
  review; it must not by itself erase a promising candidate.
- **FR-12** De-duplicate by case-insensitive canonical owner/repo, flag likely mirrors, and retain
  merged provenance after redirects.

### Ranking, output, and orchestration

- **FR-13** Compute a configurable deterministic score from stars, velocity, and activity
  recency. Later LLM-derived usefulness signals must be additive, never replace API-sourced facts.
- **FR-14** Store all pipeline data locally in SQLite and export `master_repos.csv`,
  `content_candidates.csv`, and `rejects.csv`.
- **FR-15** `master_repos.csv` shall include all enriched candidates and their status; the content
  export shall contain the top-N approved, unexported candidates. Classification/caption fields
  are intentionally absent until the later LLM phase.
- **FR-16** Lifecycle states are `discovered → enriched → scored → approved → exported`, with
  `rejected` for definitive failures. Re-scoring after configuration changes must be able to
  recover previously score-rejected repositories.
- **FR-17** `run.py` shall run `all`, `discover`, `enrich`, `score`, or `export`, safely and
  repeatedly, with per-stage counts and non-fatal per-repository errors.

## Non-functional requirements

- **NFR-1:** Every published repository statistic is GitHub API-sourced.
- **NFR-2:** Respect source rate limits with GitHub token auth, ETags/cache, bounded backoff, and
  resumable progress.
- **NFR-3:** Taxonomy edits and quality thresholds require configuration changes only.
- **NFR-4:** The local Windows/Python 3.11+ workflow requires no server and never commits secrets.
- **NFR-5:** Reddit remains optional until Data API access is approved.

## Acceptance criteria for the taxonomy refinement

1. Adding or disabling a TOML profile changes GitHub discovery without Python edits.
2. Every GitHub-discovered row identifies the profile(s) that found it.
3. A taxonomy run discovers candidates across all nine initial profiles, not merely globally
   star-ranked repositories.
4. Redirected repository names are canonicalized; `license_unknown` is auditable and does not
   trigger an automatic rejection.
5. A rerun resumes outstanding enrichment first and produces updated CSVs without duplicates.

## Deferred

OpenRouter classification, content hooks, captions, slide copy, social posting, and engagement
feedback remain later phases. The LLM will classify only taxonomy-qualified candidates and will not
be used as a source of repository facts.
