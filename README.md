# RepoScout 🔭

An autonomous research agent that scouts *amazing* open-source GitHub repos across all
domains, verifies they're high-quality and actively maintained, scores them for usefulness,
and emits a clean, deduped, post-ready dataset.

RepoScout is **standalone**. It handles `discover → enrich → score → classify → store`.
It does **not** post anything — it produces a dataset that a separate **workroom posting
pipeline** consumes to publish 3–5 repos/day. This keeps RepoScout reusable across channels.

## Docs (spec-driven)
- **[REQUIREMENTS.md](REQUIREMENTS.md)** — what it must do (FR/NFR, acceptance criteria, integration contract).
- **[DESIGN.md](DESIGN.md)** — architecture, components, SQLite schema, config, layout.
- **[TASKS.md](TASKS.md)** — milestone-by-milestone build plan traced to requirements.

## Pipeline at a glance
```
collectors (GitHub Search, HN, Reddit, awesome) → enrich (GitHub API) → score/filter+dedupe
→ store (SQLite) → export CSVs
```

## Status
✅ Deterministic v1 implemented. Run `python -m pip install -r requirements.txt`, copy
`.env.example` to `.env`, configure credentials, then run `python run.py`.

Claude classification, captions, and slide copy are deliberately deferred. The v1
`content_candidates.csv` contains only deterministic factual fields.

## Stack
Python 3.11+, SQLite (+ CSV exports), GitHub / HN / Reddit APIs, Anthropic Claude.
