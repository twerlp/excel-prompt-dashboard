#!/usr/bin/env python3
"""
SQLite-backed knowledge base for prompt evaluation experiments.

Schema:
  stories, functional_requirements, test_cases (imported ground truth)
  experiments (LLM-generated outputs + evaluation scores)
  human_reviews (manual quality assessments)
  imports (tracking which datasets were loaded)

Usage:
  from evaluation_kb import KnowledgeBase
  kb = KnowledgeBase("kb.sqlite")
  kb.initialize()
  kb.insert_story(...)
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA = """
CREATE TABLE IF NOT EXISTS stories (
    story_id      TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    domain        TEXT,
    priority      TEXT,
    story_points  INTEGER,
    sprint        TEXT,
    status        TEXT,
    dependencies  TEXT,
    user_story    TEXT NOT NULL,
    acceptance_criteria TEXT NOT NULL,
    story_text    TEXT NOT NULL,
    imported_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS functional_requirements (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id     TEXT NOT NULL REFERENCES stories(story_id),
    fr_ref       TEXT NOT NULL,
    fr_text      TEXT NOT NULL,
    source       TEXT NOT NULL CHECK(source IN ('ground_truth', 'generated')),
    experiment_id TEXT,
    imported_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS test_cases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id     TEXT NOT NULL REFERENCES stories(story_id),
    tc_id        TEXT NOT NULL,
    description  TEXT NOT NULL,
    test_type    TEXT NOT NULL,
    steps        TEXT,
    expected     TEXT,
    source       TEXT NOT NULL CHECK(source IN ('ground_truth', 'generated')),
    experiment_id TEXT,
    imported_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS experiments (
    id             TEXT PRIMARY KEY,
    story_id       TEXT NOT NULL,
    prompt_name    TEXT NOT NULL,
    category       TEXT NOT NULL CHECK(category IN ('frs', 'test_case')),
    backend        TEXT NOT NULL,
    model          TEXT NOT NULL,
    tier           INTEGER NOT NULL CHECK(tier IN (1, 2)),
    temperature    REAL DEFAULT 0.2,
    timestamp      TEXT NOT NULL,
    generated_content TEXT NOT NULL,
    generated_content_hash TEXT,
    prompt_hash    TEXT NOT NULL,

    ac_coverage             REAL,
    fr_precision            REAL,
    format_compliance       REAL,
    semantic_f1             REAL,
    completeness            REAL,
    tc_count_score          REAL,
    tc_type_diversity       REAL,
    tc_step_specificity     REAL,
    tc_expected_measurability REAL,
    tc_completeness         REAL,

    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_experiments_story ON experiments(story_id);
CREATE INDEX IF NOT EXISTS idx_experiments_prompt ON experiments(prompt_name);
CREATE INDEX IF NOT EXISTS idx_experiments_backend ON experiments(backend, model);
CREATE INDEX IF NOT EXISTS idx_experiments_category ON experiments(category);
CREATE INDEX IF NOT EXISTS idx_experiments_completeness ON experiments(completeness);

CREATE TABLE IF NOT EXISTS human_reviews (
    experiment_id  TEXT PRIMARY KEY REFERENCES experiments(id),
    reviewer       TEXT,
    score_frs      INT CHECK(score_frs BETWEEN 1 AND 5),
    score_tc       INT CHECK(score_tc BETWEEN 1 AND 5),
    notes          TEXT,
    reviewed_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS imports (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    filename       TEXT NOT NULL,
    stories_count  INTEGER,
    fr_count       INTEGER,
    tc_count       INTEGER,
    warnings       INTEGER DEFAULT 0,
    errors         INTEGER DEFAULT 0,
    imported_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class KnowledgeBase:
    """Query and manage the prompt evaluation knowledge base."""

    def __init__(self, db_path: str = "kb.sqlite"):
        self.db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def initialize(self) -> None:
        """Create all tables if they don't exist."""
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Stories ────────────────────────────────────────────────────────

    def story_exists(self, story_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM stories WHERE story_id = ?", (story_id,)
        ).fetchone()
        return row is not None

    def insert_story(self, story: Dict[str, Any], mode: str = "skip") -> bool:
        """Insert a story. mode='skip' ignores duplicates; 'upsert' replaces."""
        exists = self.story_exists(story["story_id"])
        if exists and mode == "skip":
            return False
        if exists and mode == "upsert":
            self.conn.execute(
                "DELETE FROM stories WHERE story_id = ?",
                (story["story_id"],),
            )
        story_text = story.get("story_text") or (
            story.get("user_story", "") + "\n" + story.get("acceptance_criteria", "")
        )
        self.conn.execute(
            """INSERT INTO stories
               (story_id, title, domain, priority, story_points,
                sprint, status, dependencies, user_story,
                acceptance_criteria, story_text)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                story["story_id"],
                story["title"],
                story.get("domain"),
                story.get("priority"),
                story.get("story_points"),
                story.get("sprint"),
                story.get("status"),
                story.get("dependencies"),
                story["user_story"],
                story.get("acceptance_criteria", ""),
                story_text,
            ),
        )
        self.conn.commit()
        return True

    def get_story(self, story_id: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            "SELECT * FROM stories WHERE story_id = ?", (story_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_stories(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        if domain:
            rows = self.conn.execute(
                "SELECT * FROM stories WHERE domain = ? ORDER BY story_id",
                (domain,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM stories ORDER BY story_id"
            ).fetchall()
        return [dict(r) for r in rows]

    def story_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM stories").fetchone()
        return row["cnt"] if row else 0

    # ── FR / TC ground truth ───────────────────────────────────────────

    def insert_frs(self, frs: List[Dict[str, Any]], source: str = "ground_truth") -> int:
        count = 0
        for fr in frs:
            self.conn.execute(
                """INSERT INTO functional_requirements
                   (story_id, fr_ref, fr_text, source)
                   VALUES (?, ?, ?, ?)""",
                (fr["story_id"], fr["fr_ref"], fr["fr_text"], source),
            )
            count += 1
        self.conn.commit()
        return count

    def insert_test_cases(self, tcs: List[Dict[str, Any]], source: str = "ground_truth") -> int:
        count = 0
        for tc in tcs:
            self.conn.execute(
                """INSERT INTO test_cases
                   (story_id, tc_id, description, test_type, steps, expected, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    tc["story_id"], tc["tc_id"], tc["description"],
                    tc["test_type"], tc.get("steps", ""), tc.get("expected", ""),
                    source,
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def get_ground_truth_frs(self, story_id: str) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT fr_ref, fr_text FROM functional_requirements
               WHERE story_id = ? AND source = 'ground_truth'
               ORDER BY fr_ref""",
            (story_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_ground_truth_tcs(self, story_id: str) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT tc_id, description, test_type, steps, expected
               FROM test_cases
               WHERE story_id = ? AND source = 'ground_truth'
               ORDER BY tc_id""",
            (story_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Experiments ────────────────────────────────────────────────────

    def insert_experiment(self, exp: Dict[str, Any]) -> str:
        exp_id = exp.get("id") or str(uuid.uuid4())
        self.conn.execute(
            """INSERT OR REPLACE INTO experiments
               (id, story_id, prompt_name, category, backend, model, tier,
                temperature, timestamp, generated_content,
                generated_content_hash, prompt_hash,
                ac_coverage, fr_precision, format_compliance,
                semantic_f1, completeness,
                tc_count_score, tc_type_diversity,
                tc_step_specificity, tc_expected_measurability,
                tc_completeness, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                exp_id,
                exp["story_id"],
                exp["prompt_name"],
                exp["category"],
                exp["backend"],
                exp["model"],
                exp["tier"],
                exp.get("temperature", 0.2),
                exp.get("timestamp", datetime.now(timezone.utc).isoformat()),
                exp["generated_content"],
                exp.get("generated_content_hash"),
                exp.get("prompt_hash", ""),
                exp.get("ac_coverage"),
                exp.get("fr_precision"),
                exp.get("format_compliance"),
                exp.get("semantic_f1"),
                exp.get("completeness"),
                exp.get("tc_count_score"),
                exp.get("tc_type_diversity"),
                exp.get("tc_step_specificity"),
                exp.get("tc_expected_measurability"),
                exp.get("tc_completeness"),
                exp.get("error"),
            ),
        )
        self.conn.commit()
        return exp_id

    def insert_generated_frs(self, story_id: str, experiment_id: str,
                              fr_lines: str) -> int:
        count = 0
        for line in fr_lines.split("\n"):
            line = line.strip()
            if not line or not line.startswith("FR-"):
                continue
            if ":" in line:
                fr_ref, fr_text = line.split(":", 1)
            else:
                fr_ref, fr_text = "", line
            self.conn.execute(
                """INSERT INTO functional_requirements
                   (story_id, fr_ref, fr_text, source, experiment_id)
                   VALUES (?, ?, ?, 'generated', ?)""",
                (story_id, fr_ref.strip(), fr_text.strip(), experiment_id),
            )
            count += 1
        self.conn.commit()
        return count

    def insert_generated_tcs(self, story_id: str, experiment_id: str,
                              tcs: List[Dict[str, Any]]) -> int:
        count = 0
        for tc in tcs:
            self.conn.execute(
                """INSERT INTO test_cases
                   (story_id, tc_id, description, test_type, steps, expected,
                    source, experiment_id)
                   VALUES (?, ?, ?, ?, ?, ?, 'generated', ?)""",
                (
                    story_id,
                    tc.get("tc_id", ""),
                    tc.get("description", ""),
                    tc.get("test_type", ""),
                    tc.get("steps", ""),
                    tc.get("expected", ""),
                    experiment_id,
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def get_experiments_by_story(self, story_id: str) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT * FROM experiments
               WHERE story_id = ?
               ORDER BY category, tier, prompt_name""",
            (story_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def query_best_prompt(self, category: str, domain: Optional[str] = None,
                           metric: str = "completeness") -> List[Tuple[str, float]]:
        query = """
            SELECT e.prompt_name,
                   AVG(e.{metric}) as avg_score,
                   COUNT(*) as n
            FROM experiments e
            JOIN stories s ON e.story_id = s.story_id
            WHERE e.category = ?
              AND e.{metric} IS NOT NULL
        """.format(metric=metric)
        params: List[Any] = [category]
        if domain:
            query += "  AND s.domain = ?"
            params.append(domain)
        query += " GROUP BY e.prompt_name ORDER BY avg_score DESC"
        rows = self.conn.execute(query, params).fetchall()
        return [(r["prompt_name"], r["avg_score"]) for r in rows]

    # ── Human Reviews ──────────────────────────────────────────────────

    def upsert_human_review(self, experiment_id: str, reviewer: str,
                            score_frs: int, score_tc: int,
                            notes: str = "") -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO human_reviews
               (experiment_id, reviewer, score_frs, score_tc, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (experiment_id, reviewer, score_frs, score_tc, notes),
        )
        self.conn.commit()

    # ── Import tracking ────────────────────────────────────────────────

    def record_import(self, filename: str, stories_count: int,
                      fr_count: int, tc_count: int,
                      warnings: int = 0, errors: int = 0) -> int:
        cur = self.conn.execute(
            """INSERT INTO imports (filename, stories_count, fr_count,
                                    tc_count, warnings, errors)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (filename, stories_count, fr_count, tc_count, warnings, errors),
        )
        self.conn.commit()
        return cur.lastrowid or 0

    # ── Graph ──────────────────────────────────────────────────────────

    def build_graph(self):
        """
        Build a NetworkX DiGraph from the current KB state.

        The graph captures relationships between stories, acceptance
        criteria, experiments, prompts, generated FRs/TCs, and
        evaluation scores — enabling graph-aware prompt selection
        and coverage analysis.
        """
        from graph_queries import build_graph
        return build_graph(self.db_path)
