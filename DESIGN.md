# RepoScout — Design

**Status:** Draft v1 · **Date:** 2026-07-23
Implements [REQUIREMENTS.md](REQUIREMENTS.md). Task breakdown in [TASKS.md](TASKS.md).

---

## 1. Overview

RepoScout is a **deterministic pipeline with an LLM classification stage**, wrapped as a
runnable/schedulable agent. The discovery/enrichment/scoring core is deterministic (cheap,
testable, reproducible); Claude is used only where judgement/copywriting is needed
(classification + post copy). An optional **agentic discovery mode** (Phase 3) can point an
LLM loop at novel sources, but the MVP does not depend on it.

```
 collectors/*  ─┐
                ├─▶ enrich ─▶ score/filter+dedupe ─▶ classify(LLM) ─▶ store ─▶ export CSV
 (github, hn,  ─┘
  reddit, awesome)          (GitHub API)     (config weights)   (Claude)   (SQLite)
```

Design principle: **each stage reads and writes the DB.** Stages are independent and
idempotent, so `run.py <stage>` can re-run any single step (FR-18, NFR-3).

---

## 2. Components

### 2.1 Collectors (`pipeline/collectors/`) — FR-1..4
Each collector implements a common interface:

```python
class Collector(Protocol):
    name: str
    def discover(self, cfg: Config) -> Iterable[Candidate]: ...

@dataclass
class Candidate:
    owner: str
    repo: str
    source: str          # "github_trending" | "hn" | "reddit" | "awesome"
    source_url: str
    context_text: str     # HN title / reddit post / list line — reused by the LLM hook step
    discovered_at: datetime
```

- `github_trending.py` — scrape `github.com/trending` (overall + per language).
- `github_search.py` — REST `/search/repositories`, e.g. `stars:>1000 pushed:>=<date>`,
  paginated, sorted by stars/updated.
- `hn.py` — Algolia `search?query=github.com&tags=show_hn&numericFilters=points>50`.
- `reddit.py` — PRAW; top/hot from a configurable subreddit list; extract `github.com/...` links.
- `awesome.py` — fetch curated `awesome-*` READMEs (GitHub raw), regex out repo links.

New source = new file implementing `Collector`; registered in `collectors/__init__.py` (NFR-4).

### 2.2 Enricher (`pipeline/enrich.py`) — FR-5..7
- Resolves each `Candidate` to a GitHub repo via GraphQL (batchable) or REST.
- Writes/updates the `repos` row; appends a `star_snapshots` row for velocity.
- Uses ETag conditional requests + on-disk cache; exponential backoff on 403/429 (NFR-2).
- Never aborts the run on one failure — logs and continues (NFR-6).

### 2.3 Scorer (`pipeline/score.py`) — FR-8..11
- **Hard filters** first (drop): `stars < MIN_STARS`, stale > `MAX_STALE_DAYS`, no OSI license,
  archived, empty README.
- **Score** the survivors:
  ```
  score =  w_stars   * log10(stars)
         + w_moment  * norm(stars_30d)
         + w_replace * has_paid_replacement
         + w_recency * recency(pushed_at)
         + w_hook    * hook_strength     # 0..1, filled by classifier; 0 pre-classification
  ```
- **Dedupe:** PK `full_name` (lowercased). Fuzzy mirror check on homepage + name similarity.
- Weights/thresholds live in `config.py` (FR-11).

### 2.4 Classifier (`pipeline/classify.py`) — FR-12,13
- Input: `description + readme_summary + context_text`.
- Claude returns validated JSON (pydantic): `domain, hook, replaces, value_prop, caption,
  slide_copy[]`. `slide_copy` encodes the proven template
  (cover → why-it-matters → per-tool: does / replaces / repo).
- Models: `claude-sonnet-5` for bulk; `claude-opus-4-8` to polish the daily batch captions (NFR-5).
- Re-runnable per repo or per batch (FR-13).

### 2.5 Store + export (`pipeline/store.py`) — FR-14..17
- Owns the SQLite schema, migrations, upserts, status transitions, and CSV export.
- Exports `master_repos.csv`, `content_candidates.csv` (the §7 integration contract),
  `rejects.csv`.
- `get_daily_batch(date, n)` returns top-N unexported approved repos (FR-17).

### 2.6 Orchestrator (`pipeline/run.py`) — FR-18,19
- CLI: `python run.py [all|discover|enrich|score|classify|export]` `[--source X] [--limit N]`.
- Logs per-stage counts; exit code non-zero only on fatal (config/credential) errors.
- Schedulable via Task Scheduler / cron / GitHub Action.

---

## 3. Data model (SQLite)

```sql
CREATE TABLE repos (
  full_name      TEXT PRIMARY KEY,   -- owner/repo, lowercased
  owner TEXT, name TEXT, url TEXT,
  description TEXT, homepage TEXT,
  stars INTEGER, forks INTEGER, open_issues INTEGER,
  pushed_at DATE, created_at DATE,
  license TEXT, language TEXT, topics TEXT,   -- topics = JSON array
  readme_summary TEXT,
  is_archived INTEGER DEFAULT 0,
  score REAL,
  status TEXT DEFAULT 'discovered',
  enriched_at DATETIME
);

CREATE TABLE star_snapshots (            -- FR-6, velocity
  full_name TEXT, day DATE, stars INTEGER,
  PRIMARY KEY (full_name, day)
);

CREATE TABLE sources (                   -- FR-4, provenance (many per repo)
  full_name TEXT, source TEXT, source_url TEXT,
  context_text TEXT, discovered_at DATETIME,
  PRIMARY KEY (full_name, source, source_url)
);

CREATE TABLE classification (            -- FR-12
  full_name TEXT PRIMARY KEY,
  domain TEXT, hook TEXT, replaces TEXT,
  value_prop TEXT, caption TEXT, slide_copy TEXT   -- JSON
);
```

`status` lifecycle (FR-16):
`discovered → enriched → scored → classified → approved → exported`  (or `rejected`).

---

## 4. Config (`pipeline/config.py`)

```python
MIN_STARS       = 1000          # hard floor
MAX_STALE_DAYS  = 90            # activity window
SUBREDDITS      = ["selfhosted","opensource","coolgithubprojects",
                   "LocalLLaMA","SideProject","DataHoarder"]
AWESOME_LISTS   = ["sindresorhus/awesome", ...]
SOURCES_ENABLED = {"github_trending":True,"github_search":True,"hn":True,
                   "reddit":True,"awesome":True}
WEIGHTS = {"stars":1.0,"moment":1.5,"replace":1.2,"recency":1.0,"hook":1.0}
DAILY_BATCH_N   = 5
```
Everything tunable here so behaviour changes need no code edit (FR-11, NFR-4).

---

## 5. Tech stack & layout

Python 3.11+, `httpx`, `PRAW`, `sqlite3` (stdlib), `anthropic`, `pydantic`, `python-dotenv`.

```
repo-scout/
├─ REQUIREMENTS.md  DESIGN.md  TASKS.md  README.md
├─ .env.example                      # documents required keys
├─ .gitignore                        # .env, db.sqlite, exports/, __pycache__
├─ requirements.txt
├─ pipeline/
│  ├─ run.py            # orchestrator / CLI
│  ├─ config.py
│  ├─ models.py         # Candidate, dataclasses, pydantic schemas
│  ├─ collectors/       # github_trending.py, github_search.py, hn.py, reddit.py, awesome.py, __init__.py
│  ├─ enrich.py
│  ├─ score.py
│  ├─ classify.py
│  ├─ store.py          # schema + upserts + CSV export
│  └─ github_api.py     # shared GitHub client (auth, ETag cache, backoff)
├─ exports/             # generated CSVs (gitignored)
└─ tests/               # unit tests for score/dedupe/parsers
```

---

## 6. Integration with the workroom pipeline

RepoScout is a **library + CLI**, not coupled to posting. The posting pipeline integrates via
the stable contract (REQUIREMENTS §7):
- read `exports/content_candidates.csv`, **or**
- `from pipeline.store import get_daily_batch; rows = get_daily_batch(date, n)`.

RepoScout marks handed-off rows `exported`; anything post-hand-off (captioning final images,
scheduling, publishing, engagement capture) belongs to the workroom side. This keeps RepoScout
reusable for other channels (X, newsletter) without change.

---

## 7. Cross-cutting concerns

- **Rate limiting (NFR-2):** central `github_api.py` — token auth, ETag cache, 429 backoff,
  GraphQL batching for enrichment.
- **Idempotency (NFR-3):** upserts keyed on PKs; status transitions are monotonic.
- **Resilience (NFR-6):** per-repo try/except; failures logged to `rejects`/log, run continues.
- **Testing:** pure functions (score, dedupe, link-extraction, JSON validation) unit-tested;
  collectors tested against recorded fixtures (no live calls in CI).

---

## 8. Open design questions

1. **Velocity source** — daily `star_snapshots` (simple, needs history to accrue) vs a
   star-history API (instant but external dep). *Lean: snapshots; seed once from star-history.*
2. **Enrichment transport** — REST (simple) vs GraphQL (fewer calls, more code). *Lean: REST for
   MVP, GraphQL if rate limits bite.*
3. **Approval** — auto-approve above a score cutoff vs manual review of `master_repos.csv`.
   *Lean: manual for first weeks to calibrate, then auto-approve threshold.*
4. Depends on the three operator decisions in the parent spec (posting targets, `MIN_STARS`, CTA).
