from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from pipeline.models import Candidate
from pipeline.score import score
from pipeline.store import Store


def _enriched(store: Store, full_name: str, stars: int = 1000) -> None:
    store.update_repo(full_name, {
        "stars": stars, "pushed_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "license": "MIT", "license_is_osi": 1, "readme_summary": "Useful project", "is_archived": 0,
    })
    store.set_status(full_name, "enriched")


def test_store_is_idempotent_retains_provenance_and_exports(cfg):
    with Store(cfg.db_path) as store:
        candidate = Candidate.create("Acme", "Tool", "hn", "https://hn/1", "first")
        store.upsert_candidate(candidate); store.upsert_candidate(candidate)
        store.upsert_candidate(Candidate.create("Acme", "Tool", "reddit", "https://reddit/1", "second"))
        _enriched(store, candidate.full_name, stars=1100)
        stats = score(store, cfg)
        assert stats["approved"] == 1
        assert store.conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 2
        result = store.export_csvs(cfg.exports_dir)
        assert result["content_candidates"] == 1
        assert store.get_repo(candidate.full_name)["status"] == "exported"
    assert (cfg.exports_dir / "master_repos.csv").exists()
    assert "caption" not in (cfg.exports_dir / "content_candidates.csv").read_text(encoding="utf-8").splitlines()[0]
    assert (cfg.exports_dir / "rejects.csv").read_text(encoding="utf-8").splitlines()[0] == "full_name,stage,reason,rejected_at"


def test_filters_and_auto_approval_boundary(cfg):
    with Store(cfg.db_path) as store:
        rejected = Candidate.create("Acme", "Rejected", "hn", "https://hn/2")
        approved = Candidate.create("Acme", "Approved", "hn", "https://hn/3")
        store.upsert_candidate(rejected); store.upsert_candidate(approved)
        _enriched(store, rejected.full_name, stars=999)
        _enriched(store, approved.full_name, stars=10_000)
        stats = score(store, cfg)
        assert stats["rejected"] == 1
        assert store.get_repo(rejected.full_name)["status"] == "rejected"
        assert store.get_repo(approved.full_name)["score"] >= cfg.auto_approve_score
        assert store.get_repo(approved.full_name)["status"] == "approved"


def test_exact_auto_approval_cutoff_is_inclusive(cfg):
    with Store(cfg.db_path) as store:
        candidate = Candidate.create("Acme", "Boundary", "hn", "https://hn/boundary")
        store.upsert_candidate(candidate)
        store.set_score_outcome(candidate.full_name, cfg.auto_approve_score, approved=True)
        assert store.get_repo(candidate.full_name)["status"] == "approved"


def test_snapshot_is_unique_and_status_is_monotonic(cfg):
    with Store(cfg.db_path) as store:
        candidate = Candidate.create("Acme", "Tool", "hn", "https://hn/1")
        store.upsert_candidate(candidate)
        store.record_star_snapshot(candidate.full_name, 100); store.record_star_snapshot(candidate.full_name, 101)
        assert store.conn.execute("SELECT COUNT(*) FROM star_snapshots").fetchone()[0] == 1
        store.set_status(candidate.full_name, "enriched"); store.set_status(candidate.full_name, "discovered")
        assert store.get_repo(candidate.full_name)["status"] == "enriched"


def test_velocity_requires_a_30_day_baseline(cfg):
    with Store(cfg.db_path) as store:
        candidate = Candidate.create("Acme", "Velocity", "hn", "https://hn/velocity")
        store.upsert_candidate(candidate)
        today = date.today()
        store.record_star_snapshot(candidate.full_name, 100, today - timedelta(days=29))
        store.record_star_snapshot(candidate.full_name, 120, today)
        assert store.star_velocity(candidate.full_name) == 0
        store.record_star_snapshot(candidate.full_name, 90, today - timedelta(days=30))
        assert store.star_velocity(candidate.full_name) == 30
