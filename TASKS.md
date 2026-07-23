# RepoScout — Tasks

**Status:** Deterministic v1 complete; taxonomy refinement next · **Date:** 2026-07-23

Legend: `[x]` complete · `[~]` current · `[ ]` planned

## Completed deterministic v1

- [x] Local Python scaffold, `.env` handling, ignored runtime state, and test setup.
- [x] SQLite store, provenance, snapshots, rejection audit, CSV exports, and daily-batch API.
- [x] GitHub REST enrichment with token auth, ETag cache, retry, and resumable ordering.
- [x] GitHub Search, HN, Reddit, and awesome-list collectors.
- [x] Deterministic filtering, scoring, auto-approval, dedupe/mirror flagging, and CLI stages.
- [x] First live baseline collection and export.
- [x] Editable `config/discovery_taxonomy.toml` with nine AI-agent/operator-tooling profiles.

## Milestone: taxonomy refinement

- [~] Align discovery, screening, and approval behavior with the taxonomy requirements.
- [ ] Add a migration for `license_status` (`verified_osi`, `unknown`, `non_osi`) and review flags.
- [ ] Treat `NOASSERTION` as reviewable metadata, not an automatic hard rejection.
- [ ] Canonicalize GitHub redirects/renames while preserving sources, snapshots, and state.
- [ ] Add per-profile stage metrics and report them in CLI output.
- [ ] Add tests for redirect merge, unknown licence, profile-level counts, and score recovery.
- [ ] Calibrate retrieval and approval thresholds using a small live run from each profile.
- [ ] Run the taxonomy collection, review `master_repos.csv`, and tune TOML queries/verticals.

## Later milestones

- [ ] Enable Reddit after Data API approval; validate rate limits and provenance.
- [ ] Add OpenRouter structured classification for taxonomy-qualified candidates only.
- [ ] Add `domain`, usefulness rationale, paid alternative, hook, and confidence to classification.
- [ ] Add caption/slide-copy generation only after classification quality is calibrated.
- [ ] Add Windows Task Scheduler / GitHub Actions scheduling and run metrics retention.

## Acceptance for the next implementation step

- The taxonomy file remains the only place required to add a discovery niche or query.
- A redirected repo is stored under its canonical GitHub name without losing provenance.
- Unknown licence metadata is flagged for review but remains visible and scoreable.
- CLI output exposes counts by taxonomy profile and the CSVs remain backward-compatible.
