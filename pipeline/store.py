"""SQLite persistence, lifecycle management, and CSV exports."""
from __future__ import annotations

import csv
import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .models import Candidate


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS repos (
  full_name TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL, url TEXT,
  description TEXT, homepage TEXT, stars INTEGER, forks INTEGER, open_issues INTEGER,
  pushed_at TEXT, created_at TEXT, license TEXT, license_is_osi INTEGER,
  language TEXT, topics TEXT NOT NULL DEFAULT '[]', readme_summary TEXT,
  is_archived INTEGER NOT NULL DEFAULT 0, is_mirror INTEGER NOT NULL DEFAULT 0,
  score REAL, status TEXT NOT NULL DEFAULT 'discovered', enriched_at TEXT,
  approved_at TEXT, exported_at TEXT,
  CHECK(status IN ('discovered','enriched','scored','approved','exported','rejected'))
);
CREATE TABLE IF NOT EXISTS sources (
  full_name TEXT NOT NULL REFERENCES repos(full_name), source TEXT NOT NULL,
  source_url TEXT NOT NULL, context_text TEXT NOT NULL DEFAULT '', discovered_at TEXT NOT NULL,
  PRIMARY KEY(full_name, source, source_url)
);
CREATE TABLE IF NOT EXISTS star_snapshots (
  full_name TEXT NOT NULL REFERENCES repos(full_name), day TEXT NOT NULL, stars INTEGER NOT NULL,
  PRIMARY KEY(full_name, day)
);
CREATE TABLE IF NOT EXISTS rejections (
  id INTEGER PRIMARY KEY, full_name TEXT NOT NULL REFERENCES repos(full_name), stage TEXT NOT NULL,
  reason TEXT NOT NULL, rejected_at TEXT NOT NULL, UNIQUE(full_name, stage, reason)
);
-- Reserved for the later LLM-based classification release.
CREATE TABLE IF NOT EXISTS classification (
  full_name TEXT PRIMARY KEY REFERENCES repos(full_name), domain TEXT, hook TEXT,
  replaces TEXT, value_prop TEXT, caption TEXT, slide_copy TEXT, classified_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_repos_status_score ON repos(status, score DESC);
CREATE INDEX IF NOT EXISTS idx_sources_full_name ON sources(full_name);
"""

STATUS_RANK = {"discovered": 0, "enriched": 1, "scored": 2, "approved": 3, "exported": 4, "rejected": 99}


class Store:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def upsert_candidate(self, candidate: Candidate) -> None:
        self.conn.execute(
            "INSERT INTO repos(full_name, owner, name, url) VALUES (?, ?, ?, ?) ON CONFLICT(full_name) DO NOTHING",
            (candidate.full_name, candidate.owner, candidate.repo, f"https://github.com/{candidate.owner}/{candidate.repo}"),
        )
        self.conn.execute(
            """INSERT INTO sources(full_name, source, source_url, context_text, discovered_at) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(full_name, source, source_url) DO UPDATE SET
               context_text=excluded.context_text, discovered_at=excluded.discovered_at""",
            (candidate.full_name, candidate.source, candidate.source_url, candidate.context_text, candidate.discovered_at.isoformat()),
        )
        self.conn.commit()

    def update_repo(self, full_name: str, fields: dict[str, Any]) -> None:
        allowed = {"owner", "name", "url", "description", "homepage", "stars", "forks", "open_issues", "pushed_at",
                   "created_at", "license", "license_is_osi", "language", "topics", "readme_summary", "is_archived",
                   "is_mirror", "score", "enriched_at", "approved_at", "exported_at"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Unknown repo columns: {sorted(unknown)}")
        if not fields:
            return
        values = dict(fields)
        if "topics" in values and not isinstance(values["topics"], str):
            values["topics"] = json.dumps(values["topics"])
        assignments = ", ".join(f"{key}=?" for key in values)
        cursor = self.conn.execute(f"UPDATE repos SET {assignments} WHERE full_name=?", (*values.values(), full_name.lower()))
        if cursor.rowcount != 1:
            raise KeyError(full_name)
        self.conn.commit()

    def record_star_snapshot(self, full_name: str, stars: int, day: date | None = None) -> None:
        self.conn.execute(
            """INSERT INTO star_snapshots(full_name, day, stars) VALUES (?, ?, ?)
               ON CONFLICT(full_name, day) DO UPDATE SET stars=excluded.stars""",
            (full_name.lower(), (day or date.today()).isoformat(), stars),
        )
        self.conn.commit()

    def set_status(self, full_name: str, status: str) -> None:
        if status not in STATUS_RANK:
            raise ValueError(f"Invalid status: {status}")
        row = self.get_repo(full_name)
        if not row:
            raise KeyError(full_name)
        old = row["status"]
        if old == "exported" and status != "exported":
            return
        if old != "rejected" and status != "rejected" and STATUS_RANK[status] < STATUS_RANK[old]:
            return
        values: dict[str, Any] = {"status": status}
        if status == "approved": values["approved_at"] = self._now()
        if status == "exported": values["exported_at"] = self._now()
        assignments = ", ".join(f"{key}=?" for key in values)
        self.conn.execute(f"UPDATE repos SET {assignments} WHERE full_name=?", (*values.values(), full_name.lower()))
        self.conn.commit()

    def reject(self, full_name: str, stage: str, reasons: Iterable[str]) -> None:
        for reason in sorted(set(reasons)):
            self.conn.execute(
                """INSERT INTO rejections(full_name, stage, reason, rejected_at) VALUES (?, ?, ?, ?)
                   ON CONFLICT(full_name, stage, reason) DO UPDATE SET rejected_at=excluded.rejected_at""",
                (full_name.lower(), stage, reason, self._now()),
            )
        self.conn.commit()
        self.set_status(full_name, "rejected")

    def get_repo(self, full_name: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM repos WHERE full_name=?", (full_name.lower(),)).fetchone()

    def repos_for_status(self, statuses: Iterable[str]) -> list[sqlite3.Row]:
        values = tuple(statuses)
        return self.conn.execute(
            f"SELECT * FROM repos WHERE status IN ({','.join('?' for _ in values)}) ORDER BY full_name", values
        ).fetchall()

    def repos_for_enrichment(self) -> list[sqlite3.Row]:
        # Work through never-enriched rows first so an interrupted run resumes instead
        # of repeatedly spending its budget on the alphabetically first repositories.
        return self.conn.execute(
            """SELECT * FROM repos
               WHERE status NOT IN ('rejected', 'exported')
               ORDER BY CASE WHEN enriched_at IS NULL THEN 0 ELSE 1 END,
                        enriched_at ASC, full_name ASC"""
        ).fetchall()

    def set_score_outcome(self, full_name: str, score: float, approved: bool) -> None:
        """Refresh a non-final scoring decision (config changes may change approval)."""
        row = self.get_repo(full_name)
        if not row or row["status"] == "exported":
            return
        status = "approved" if approved else "scored"
        self.conn.execute(
            "UPDATE repos SET score=?, status=?, approved_at=? WHERE full_name=?",
            (score, status, self._now() if approved else None, full_name.lower()),
        )
        self.conn.commit()

    def star_velocity(self, full_name: str) -> int:
        latest = self.conn.execute(
            "SELECT day, stars FROM star_snapshots WHERE full_name=? ORDER BY day DESC LIMIT 1", (full_name.lower(),)
        ).fetchone()
        if not latest:
            return 0
        baseline = self.conn.execute(
            """SELECT stars FROM star_snapshots
               WHERE full_name=? AND day<=date(?, '-30 days') ORDER BY day DESC LIMIT 1""",
            (full_name.lower(), latest["day"]),
        ).fetchone()
        return 0 if not baseline else max(0, int(latest["stars"]) - int(baseline["stars"]))

    def find_probable_mirrors(self) -> list[str]:
        rows = self.conn.execute("SELECT full_name, homepage, name FROM repos WHERE homepage IS NOT NULL AND homepage != ''").fetchall()
        mirrors: set[str] = set()
        for index, row in enumerate(rows):
            for other in rows[index + 1:]:
                same_homepage = row["homepage"].rstrip("/").lower() == other["homepage"].rstrip("/").lower()
                if same_homepage and row["name"].lower() != other["name"].lower():
                    mirrors.add(other["full_name"])
        for full_name in mirrors: self.update_repo(full_name, {"is_mirror": 1})
        return sorted(mirrors)

    def get_daily_batch(self, batch_day: date | str, n: int) -> list[dict[str, Any]]:
        _ = str(batch_day)  # Future date-specific scheduling policy.
        rows = self.conn.execute("SELECT * FROM repos WHERE status='approved' ORDER BY score DESC, stars DESC LIMIT ?", (n,)).fetchall()
        return [dict(row) for row in rows]

    def export_csvs(self, exports_dir: Path | str, batch_size: int = 5) -> dict[str, int]:
        directory = Path(exports_dir); directory.mkdir(parents=True, exist_ok=True)
        master = [dict(row) for row in self.conn.execute("SELECT * FROM repos ORDER BY score DESC, stars DESC, full_name").fetchall()]
        candidates = self.get_daily_batch(date.today(), batch_size)
        rejects = [dict(row) for row in self.conn.execute("SELECT full_name, stage, reason, rejected_at FROM rejections ORDER BY rejected_at DESC, full_name").fetchall()]
        self._write_csv(directory / "master_repos.csv", master)
        self._write_csv(directory / "content_candidates.csv", candidates)
        self._write_csv(directory / "rejects.csv", rejects, ["full_name", "stage", "reason", "rejected_at"])
        for candidate in candidates:
            self.set_status(candidate["full_name"], "exported")
        return {"master": len(master), "content_candidates": len(candidates), "rejects": len(rejects)}

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, Any]], default_fields: list[str] | None = None) -> None:
        fields = list(rows[0]) if rows else (default_fields or ["full_name", "url", "description", "homepage", "stars", "forks", "open_issues", "pushed_at", "license", "language", "topics", "score", "status"])
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader(); writer.writerows(rows)


def get_daily_batch(db_path: Path | str, batch_day: date | str, n: int) -> list[dict[str, Any]]:
    with Store(db_path) as store:
        return store.get_daily_batch(batch_day, n)
