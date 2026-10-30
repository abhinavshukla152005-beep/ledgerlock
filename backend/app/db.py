from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    policy_source TEXT,
    llm_source TEXT,
    codegen_source TEXT,
    currency TEXT,
    row_count INTEGER,
    quarantined_count INTEGER,
    finding_count INTEGER,
    verified INTEGER,
    containment TEXT,
    backend TEXT,
    duration_ms INTEGER,
    memo TEXT,
    quarantine TEXT,
    error TEXT
);
CREATE TABLE IF NOT EXISTS findings (
    run_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    rule TEXT NOT NULL,
    severity TEXT NOT NULL,
    txn_ids TEXT NOT NULL,
    amount REAL NOT NULL,
    message TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS steps (
    run_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT,
    duration_ms INTEGER
);
"""


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(settings.db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(SCHEMA)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(runs)")}
        if "codegen_source" not in columns:
            conn.execute("ALTER TABLE runs ADD COLUMN codegen_source TEXT")


def save_run(run: dict[str, Any]) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO runs (id, created_at, status, policy_source, llm_source, codegen_source, "
            "currency, row_count, quarantined_count, finding_count, verified, containment, backend, "
            "duration_ms, memo, quarantine, error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run["id"],
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                run["status"],
                run.get("policy_source"),
                run.get("llm_source"),
                run.get("codegen_source"),
                run.get("currency"),
                run.get("row_count", 0),
                run.get("quarantined_count", 0),
                run.get("finding_count", 0),
                int(bool(run.get("verified"))),
                run.get("containment"),
                run.get("backend"),
                run.get("duration_ms", 0),
                run.get("memo"),
                json.dumps(run.get("quarantined", [])),
                run.get("error"),
            ),
        )
        conn.executemany(
            "INSERT INTO findings (run_id, idx, rule, severity, txn_ids, amount, message) "
            "VALUES (?,?,?,?,?,?,?)",
            [
                (
                    run["id"],
                    idx,
                    f["rule"],
                    f["severity"],
                    json.dumps(f["txn_ids"]),
                    f["amount"],
                    f["message"],
                )
                for idx, f in enumerate(run.get("findings", []))
            ],
        )
        conn.executemany(
            "INSERT INTO steps (run_id, idx, name, status, detail, duration_ms) "
            "VALUES (?,?,?,?,?,?)",
            [
                (run["id"], idx, s["name"], s["status"], s.get("detail"), s.get("duration_ms", 0))
                for idx, s in enumerate(run.get("steps", []))
            ],
        )


def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, created_at, status, finding_count, quarantined_count, verified, "
            "duration_ms FROM runs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [{**dict(row), "verified": bool(row["verified"])} for row in rows]


def get_run(run_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        run = dict(row)
        findings = conn.execute(
            "SELECT rule, severity, txn_ids, amount, message FROM findings "
            "WHERE run_id = ? ORDER BY idx",
            (run_id,),
        ).fetchall()
        steps = conn.execute(
            "SELECT name, status, detail, duration_ms FROM steps WHERE run_id = ? ORDER BY idx",
            (run_id,),
        ).fetchall()
    run["findings"] = [{**dict(f), "txn_ids": json.loads(f["txn_ids"])} for f in findings]
    run["steps"] = [dict(s) for s in steps]
    run["quarantined"] = json.loads(run.pop("quarantine") or "[]")
    run["verified"] = bool(run["verified"])
    return run
