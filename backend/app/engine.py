"""Deterministic reference engine.

Host-side source of truth. The sandboxed checker is generated separately, and the
verifier diffs its output against this implementation.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date, timedelta
from typing import Any

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(the\s+)?(policy|policies|rules|instructions)",
    r"(^|\n)\s*system\s*:",
    r"you\s+are\s+now\s+",
    r"approve\s+(all|every|this)\b",
    r"mark\s+(this|all|it)\s+as\s+(compliant|approved)",
    r"do\s+not\s+(flag|report|audit)\b",
    r"new\s+instructions?\s*:",
    r"override\s+(the\s+)?(policy|rules|limits)",
]

REQUIRED_COLUMNS = {
    "txn_id",
    "date",
    "vendor",
    "category",
    "amount",
    "currency",
    "receipt_attached",
    "approver",
    "note",
}

DEFAULT_RULES: dict[str, Any] = {
    "currency": "INR",
    "category_caps": {"meals": 1500, "hotel": 6000, "software": 2500, "transport": 800},
    "meals_daily_cap": 2500,
    "receipt_required_above": 1000,
    "approval_required_above": 5000,
    "duplicate_window_days": 7,
}


def scan_for_injection(text: str) -> list[str]:
    if not text:
        return []
    hits: list[str] = []
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            hits.append(pattern)
    return hits


def _parse_bool(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def parse_rows(csv_text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"missing columns: {', '.join(sorted(missing))}")
    rows: list[dict[str, Any]] = []
    for raw in reader:
        rows.append(
            {
                "txn_id": raw["txn_id"].strip(),
                "date": raw["date"].strip(),
                "vendor": raw["vendor"].strip(),
                "category": raw["category"].strip().lower(),
                "amount": float(raw["amount"]),
                "currency": raw["currency"].strip().upper() or "INR",
                "receipt_attached": _parse_bool(raw["receipt_attached"]),
                "approver": raw["approver"].strip(),
                "note": raw["note"].strip(),
            }
        )
    return rows


def split_quarantine(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    clean: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for row in rows:
        haystack = " ".join(str(v) for v in row.values())
        hits = scan_for_injection(haystack)
        if hits:
            quarantined.append(
                {
                    "txn_id": row["txn_id"],
                    "vendor": row["vendor"],
                    "amount": row["amount"],
                    "reason": "instruction-like text in untrusted data",
                    "matched_patterns": hits,
                }
            )
        else:
            clean.append(row)
    return clean, quarantined


def normalize_rules(raw: dict[str, Any] | None) -> dict[str, Any]:
    rules = dict(DEFAULT_RULES)
    if not raw:
        return rules
    rules["currency"] = str(raw.get("currency", rules["currency"])).upper()
    caps = raw.get("category_caps") or {}
    if isinstance(caps, dict):
        parsed = {}
        for key, value in caps.items():
            try:
                parsed[str(key).strip().lower()] = float(value)
            except (TypeError, ValueError):
                continue
        if parsed:
            rules["category_caps"] = parsed
    for key in ("meals_daily_cap", "receipt_required_above", "approval_required_above"):
        try:
            if key in raw:
                rules[key] = float(raw[key])
        except (TypeError, ValueError):
            pass
    try:
        if "duplicate_window_days" in raw:
            rules["duplicate_window_days"] = int(raw["duplicate_window_days"])
    except (TypeError, ValueError):
        pass
    return rules


def _finding(
    rule: str,
    severity: str,
    txn_ids: list[str],
    amount: float,
    message: str,
) -> dict[str, Any]:
    return {
        "rule": rule,
        "severity": severity,
        "txn_ids": txn_ids,
        "amount": round(float(amount), 2),
        "message": message,
    }


def audit(rows: list[dict[str, Any]], rules: dict[str, Any]) -> list[dict[str, Any]]:
    rules = normalize_rules(rules)
    caps = {k.lower(): float(v) for k, v in rules["category_caps"].items()}
    findings: list[dict[str, Any]] = []

    for row in rows:
        cap = caps.get(row["category"])
        if cap is not None and row["amount"] > cap:
            findings.append(
                _finding(
                    "over_category_cap",
                    "high",
                    [row["txn_id"]],
                    row["amount"],
                    f"{row['category']} spend {row['amount']:.2f} exceeds cap {cap:.2f}",
                )
            )

    meals: dict[str, float] = {}
    for row in rows:
        if row["category"] == "meals":
            meals[row["date"]] = meals.get(row["date"], 0.0) + row["amount"]
    for day, total in sorted(meals.items()):
        if total > rules["meals_daily_cap"]:
            ids = [r["txn_id"] for r in rows if r["category"] == "meals" and r["date"] == day]
            findings.append(
                _finding(
                    "meals_daily_cap",
                    "medium",
                    ids,
                    total,
                    f"meals on {day} total {total:.2f}, daily cap {rules['meals_daily_cap']:.2f}",
                )
            )

    for row in rows:
        if row["amount"] > rules["receipt_required_above"] and not row["receipt_attached"]:
            findings.append(
                _finding(
                    "missing_receipt",
                    "medium",
                    [row["txn_id"]],
                    row["amount"],
                    f"receipt required above {rules['receipt_required_above']:.2f}",
                )
            )

    for row in rows:
        if row["amount"] > rules["approval_required_above"] and not row["approver"]:
            findings.append(
                _finding(
                    "missing_approval",
                    "high",
                    [row["txn_id"]],
                    row["amount"],
                    f"approval required above {rules['approval_required_above']:.2f}",
                )
            )

    window = timedelta(days=int(rules["duplicate_window_days"]))
    by_key: dict[tuple[str, float], list[dict[str, Any]]] = {}
    for row in rows:
        by_key.setdefault((row["vendor"].lower(), round(row["amount"], 2)), []).append(row)
    for (vendor, amount), group in by_key.items():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda r: r["date"])
        for previous, current in zip(ordered, ordered[1:]):
            gap = (date.fromisoformat(current["date"]) - date.fromisoformat(previous["date"])).days
            if gap <= window.days:
                findings.append(
                    _finding(
                        "suspected_duplicate",
                        "high",
                        [previous["txn_id"], current["txn_id"]],
                        amount * 2,
                        f"{vendor} {amount:.2f} charged twice within {gap} day(s)",
                    )
                )

    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: (order.get(f["severity"], 9), -f["amount"]))
    return findings
