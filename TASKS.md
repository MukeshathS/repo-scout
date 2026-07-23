# RepoScout — Tasks

**Status:** Draft v1 · **Date:** 2026-07-23
Derived from [REQUIREMENTS.md](REQUIREMENTS.md) & [DESIGN.md](DESIGN.md).
`(FR-n)` / `(NFR-n)` tags trace each task to a requirement.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done

---

## Milestone 0 — Project scaffold
- [ ] Init git repo; add `.gitignore` (`.env`, `db.sqlite`, `exports/`, `__pycache__`) (NFR-8)
- [ ] `requirements.txt` — httpx, praw, anthropic, pydantic, python-dotenv
- [ ] `.env.example` documenting `GITHUB_TOKEN`, `REDDIT_*`, `ANTHROPIC_API_KEY` (NFR-8)
- [ ] `pipeline/config.py` with thresholds, weights, source toggles (FR-11)
- [ ] `pipeline/models.py` — `Candidate` dataclass + pydantic classification schema (FR-2,13)

## Milestone 1 — Storage layer *(build first; every stage depends on it)*
- [ ] `store.py`: create SQLite schema — `repos`, `star_snapshots`, `sources`, `classification` (FR-14)
- [ ] Upsert helpers keyed on PKs; monotonic `status` transitions (FR-7,16, NFR-3)
- [ ] CSV export: `master_repos.csv`, `content_candidates.csv`, `rejects.csv` (FR-15)
- [ ] `get_daily_batch(date, n)` (FR-17)
- [ ] Unit tests: upsert idempotency, status transitions

## Milestone 2 — GitHub client + enrichment
- [ ] `github_api.py`: token auth, ETag cache, 429/403 backoff (NFR-2)
- [ ] `enrich.py`: fetch stars/forks/issues/pushed_at/license/lang/topics/README/archived (FR-5)
- [ ] Write `star_snapshots` row per run for velocity (FR-6)
- [ ] Per-repo try/except; log + continue on failure (FR-7, NFR-6)

## Milestone 3 — Collectors (MVP sources)
- [ ] `collectors/__init__.py` — registry + `Collector` protocol (NFR-4)
- [ ] `github_trending.py` — overall + per-language (FR-1)
- [ ] `github_search.py` — `stars:>N pushed:>=date`, paginated (FR-1)
- [ ] `hn.py` — Algolia Show HN + high-points, extract github links (FR-1)
- [ ] Normalize all to `Candidate`; write provenance to `sources` (FR-2,4)
- [ ] Unit test: github-link extraction from messy text

## Milestone 4 — Scoring & dedupe
- [ ] `score.py` hard filters: stars/stale/license/archived/README (FR-8)
- [ ] Usefulness score with config weights (FR-9,11)
- [ ] Canonical dedupe on `full_name` + fuzzy mirror flag (FR-10)
- [ ] Unit tests: filter boundaries, score ordering, dedupe/mirror cases

## Milestone 5 — Orchestrator (MVP complete)
- [ ] `run.py` CLI: `all|discover|enrich|score|export`, `--source`, `--limit` (FR-18)
- [ ] Per-stage count logging + non-zero exit only on fatal errors (NFR-6)
- [ ] **✅ MVP acceptance:** `python run.py` → ranked, deduped, filtered `master_repos.csv`
      from GitHub + HN, no fabricated stats (REQUIREMENTS §8.1–8.3)

## Milestone 6 — Classification & content candidates
- [ ] `classify.py`: Claude → validated JSON (domain/hook/replaces/value_prop/caption/slide_copy) (FR-12,13)
- [ ] Cheap model bulk + premium polish for daily batch (NFR-5)
- [ ] Feed `hook_strength` back into score (DESIGN §2.3)
- [ ] Export `content_candidates.csv` per integration contract (FR-15, REQUIREMENTS §7)
- [ ] **✅ Content acceptance:** top batch has caption + slide copy (REQUIREMENTS §8.4–8.5)

## Milestone 7 — Extra sources
- [ ] `reddit.py` (PRAW, configurable subreddits) (FR-1,3)
- [ ] `awesome.py` (parse awesome-* READMEs) (FR-1)
- [ ] Backfill provenance/dedupe across all sources (FR-4,10)

## Milestone 8 — Scheduling & ops
- [ ] Schedulable run (Windows Task Scheduler / GitHub Action) (FR-19)
- [ ] Seed the DB from `../github-repos-reference.md` (the 22 vetted repos)
- [ ] Verify + fill the `find`/TBD entries in the reference swipe file
- [ ] Run log / simple metrics per run (NFR-6)

## Backlog (Phase 3+, deferred)
- [ ] Agentic discovery mode (LLM points itself at novel sources)
- [ ] X / LinkedIn / Instagram source adapters (only if a niche needs it)
- [ ] Engagement feedback loop → retune score `WEIGHTS`
- [ ] Template graphic generation (hand-off boundary — may live in workroom pipeline)

---

## First-session order of work
1. Milestone 0 → 1 (scaffold + storage)
2. Milestone 2 → 3 (enrich + GitHub/HN collectors)
3. Milestone 4 → 5 (score + orchestrator) = **runnable MVP**
4. Then Milestone 6 (content) and 7 (Reddit/awesome).

## Blocking decisions (from operator, see parent spec)
- Posting targets (IG only vs +X/LinkedIn) → affects `content_candidates.csv` shape.
- `MIN_STARS` floor (1k vs 5k) → affects volume.
- CTA style (comment-gate vs link-in-bio) → affects caption template in classify.
