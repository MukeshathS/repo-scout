# RepoScout — Requirements

**Project:** RepoScout — an autonomous research agent that scouts *amazing* open-source
GitHub repos across all domains, scores them for usefulness, and emits a clean, deduped,
post-ready dataset.
**Status:** Draft v1 · **Date:** 2026-07-23 · **Owner:** Mukesh (solo, build-in-public)

RepoScout is a **standalone project**. It owns discovery → enrichment → scoring →
classification → storage. It does **not** post anything; it produces a dataset that a
separate **workroom posting pipeline** consumes later (see §7, Integration contract).

---

## 1. Problem & goal

High-engagement social content is built around lists of genuinely useful open-source repos
("tools so good they shouldn't be free"). Finding those repos by hand doesn't scale.

**Goal:** given nothing but a schedule, RepoScout continuously surfaces high-quality,
currently-maintained, genuinely useful repos — enough to sustain **3–5 posts/day** — with
all supporting metadata verified from source APIs (no fabricated stats).

---

## 2. Actors

- **Operator (Mukesh):** runs the agent, reviews/approves candidates, tunes thresholds.
- **RepoScout agent:** the automated system described here.
- **Downstream consumer:** the workroom posting pipeline (out of scope; consumes RepoScout output).

---

## 3. Functional requirements

Written as testable statements. IDs (`FR-n`) are referenced by DESIGN and TASKS.

### Discovery
- **FR-1** The system shall collect candidate repos from GitHub Trending, GitHub Search API,
  Hacker News (Algolia), Reddit, and awesome-lists.
- **FR-2** Each collector shall normalize output to `{owner, repo, source, source_url,
  context_text, discovered_at}`.
- **FR-3** The system shall be able to run any single collector in isolation (per-source toggles).
- **FR-4** The system shall record provenance for every repo, keeping *all* sources it was
  found in (a repo found on both HN and Reddit keeps both).

### Enrichment
- **FR-5** For each candidate the system shall fetch, via the GitHub API: stars, forks,
  open issues, `pushed_at`, `created_at`, license, primary language, topics, description,
  archived flag, and a README excerpt.
- **FR-6** The system shall record a daily `stars` snapshot per repo to compute 30-day star
  velocity (momentum).
- **FR-7** Enrichment shall be idempotent and resumable — re-running updates existing rows,
  never duplicates them.

### Scoring & filtering
- **FR-8** The system shall drop any repo that fails a hard filter: stars < `MIN_STARS`,
  `pushed_at` older than `MAX_STALE_DAYS`, missing/non-OSI license, archived, or empty README.
- **FR-9** The system shall compute a configurable **usefulness score** combining stars,
  30-day velocity, recency, "replaces a paid tool", and hook strength.
- **FR-10** The system shall de-duplicate by canonical `owner/repo` (case-insensitive) and
  flag likely mirrors (same homepage / near-identical name).
- **FR-11** All thresholds and score weights shall be configurable without code changes.

### Classification (LLM)
- **FR-12** For scored repos the system shall use Claude to produce: `domain`, one-line `hook`,
  `replaces` (paid tool + est. $/mo or null), `value_prop`, and draft `caption` + `slide_copy`.
- **FR-13** Classification output shall be structured (validated JSON), and the step shall be
  re-runnable for a single repo or a batch.

### Storage & output
- **FR-14** The system shall persist everything in a local **SQLite** database (source of truth).
- **FR-15** The system shall export CSVs: `master_repos.csv` (review), `content_candidates.csv`
  (scored + classified, ready for the posting pipeline), and `rejects.csv` (audit trail).
- **FR-16** Each repo shall carry a lifecycle `status`:
  `discovered → enriched → scored → classified → approved → exported → (rejected)`.
- **FR-17** The system shall expose a "daily batch" query returning the top-N unexported,
  approved repos for a given date.

### Orchestration
- **FR-18** A single entrypoint (`run.py`) shall run the full pipeline or any named stage.
- **FR-19** The agent shall be schedulable (cron / GitHub Action) and safe to run repeatedly.

---

## 4. Non-functional requirements

- **NFR-1 (Correctness):** every published stat is API-sourced; no invented numbers.
- **NFR-2 (Rate limits):** respect GitHub (5k/hr auth), Reddit, HN limits; use auth tokens,
  caching, conditional requests (ETags); back off on 403/429.
- **NFR-3 (Idempotency):** all stages are re-runnable and converge to the same state.
- **NFR-4 (Extensibility):** adding a new source = adding one collector module implementing a
  common interface; no changes to enrich/score/store.
- **NFR-5 (Cost):** LLM cost bounded — classify only repos that pass filters; cheap model for
  bulk, premium model only for final copy polish.
- **NFR-6 (Observability):** each run logs counts per stage (discovered / enriched / kept /
  rejected / classified) and errors, without aborting the whole run on one bad repo.
- **NFR-7 (Portability):** runs locally on Windows with Python 3.11+; no server required.
- **NFR-8 (Secrets):** all credentials in `.env`, never committed.

---

## 5. Constraints & assumptions

- Phase 1 uses **clean-API sources only** — no scraping.
- Local-first: SQLite + CSV, no cloud DB.
- Single operator; no multi-user/auth concerns yet.
- Assumes valid GitHub + Reddit + Anthropic credentials are available.

---

## 6. Out of scope (for RepoScout)

- Posting / scheduling to any social platform (that's the workroom pipeline).
- Graphic/carousel image generation.
- X / LinkedIn / Instagram scraping (deferred; revisit only if a niche needs it).
- Engagement analytics ingestion (the posting pipeline may feed this back later).

---

## 7. Integration contract (how workroom consumes RepoScout)

RepoScout's deliverable to the posting pipeline is stable and explicit:

- **Primary:** `content_candidates.csv` — one row per approved repo with columns:
  `full_name, url, domain, hook, replaces, value_prop, caption, slide_copy(JSON),
  stars, stars_30d, pushed_at, license, score, status`.
- **Alternative:** direct read of the SQLite DB (`repos` ⋈ `classification` where
  `status='approved'`), or a `get_daily_batch(date, n)` function.
- RepoScout sets `status='exported'` once handed off; the posting pipeline owns everything after.

---

## 8. Acceptance criteria (MVP done =)

1. `python run.py` produces a `master_repos.csv` of ranked, deduped, filtered repos from at
   least GitHub + HN with zero fabricated stats. *(FR-1,5,8,9,10,14,15)*
2. Re-running the pipeline does not create duplicates. *(FR-7,10, NFR-3)*
3. Config change to `MIN_STARS` visibly changes the result set with no code edit. *(FR-11)*
4. A classified batch yields caption + slide copy for the top repos. *(FR-12,13)*
5. `content_candidates.csv` matches the §7 contract. *(FR-15, integration)*
