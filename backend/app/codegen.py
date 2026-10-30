"""Generates the checker script that executes inside the sandbox.

The script is self-contained: it receives sanitized rows and rules as JSON and
re-implements the checks, so the host verifier can diff two independent runs.
"""
from __future__ import annotations

import ast
import json
from typing import Any

FORBIDDEN_MODULES = {
    "socket",
    "subprocess",
    "ctypes",
    "multiprocessing",
    "http",
    "urllib",
    "requests",
}
FORBIDDEN_CALLS = {"eval", "exec", "__import__", "system", "popen"}


def validate(source: str) -> str | None:
    """Checks a model-drafted checker before it is allowed near the sandbox.

    Returns an error string, or None when the script is acceptable.
    """
    if not isinstance(source, str) or not 40 <= len(source) <= 20000:
        return "script missing or wrong size"
    if "RESULT:" not in source:
        return "script never prints the RESULT marker"
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f"syntax error: {exc.msg}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_MODULES:
                    return f"forbidden import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            if module in FORBIDDEN_MODULES:
                return f"forbidden import: {node.module}"
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name in FORBIDDEN_CALLS:
                return f"forbidden call: {name}"
    return None

TEMPLATE = '''import json
import os

RULES = {rules}

INPUT = os.environ.get("LEDGERLOCK_INPUT", "/workspace/input.json")
with open(INPUT, "r", encoding="utf-8") as handle:
    rows = json.load(handle)["rows"]

findings = []


def add(rule, severity, txn_ids, amount, message):
    findings.append(
        {{
            "rule": rule,
            "severity": severity,
            "txn_ids": txn_ids,
            "amount": round(float(amount), 2),
            "message": message,
        }}
    )


caps = {{key.lower(): float(value) for key, value in RULES["category_caps"].items()}}

for row in rows:
    cap = caps.get(row["category"])
    if cap is not None and row["amount"] > cap:
        add(
            "over_category_cap",
            "high",
            [row["txn_id"]],
            row["amount"],
            row["category"] + " spend %.2f exceeds cap %.2f" % (row["amount"], cap),
        )

meals = {{}}
for row in rows:
    if row["category"] == "meals":
        meals[row["date"]] = meals.get(row["date"], 0.0) + row["amount"]
for day in sorted(meals):
    if meals[day] > RULES["meals_daily_cap"]:
        ids = [r["txn_id"] for r in rows if r["category"] == "meals" and r["date"] == day]
        add(
            "meals_daily_cap",
            "medium",
            ids,
            meals[day],
            "meals on %s total %.2f, daily cap %.2f"
            % (day, meals[day], RULES["meals_daily_cap"]),
        )

for row in rows:
    if row["amount"] > RULES["receipt_required_above"] and not row["receipt_attached"]:
        add(
            "missing_receipt",
            "medium",
            [row["txn_id"]],
            row["amount"],
            "receipt required above %.2f" % RULES["receipt_required_above"],
        )

for row in rows:
    if row["amount"] > RULES["approval_required_above"] and not row["approver"]:
        add(
            "missing_approval",
            "high",
            [row["txn_id"]],
            row["amount"],
            "approval required above %.2f" % RULES["approval_required_above"],
        )

from datetime import date as _date

window = int(RULES["duplicate_window_days"])
groups = {{}}
for row in rows:
    groups.setdefault((row["vendor"].lower(), round(row["amount"], 2)), []).append(row)
for (vendor, amount), group in groups.items():
    if len(group) < 2:
        continue
    ordered = sorted(group, key=lambda r: r["date"])
    for previous, current in zip(ordered, ordered[1:]):
        gap = (_date.fromisoformat(current["date"]) - _date.fromisoformat(previous["date"])).days
        if gap <= window:
            add(
                "suspected_duplicate",
                "high",
                [previous["txn_id"], current["txn_id"]],
                amount * 2,
                "%s %.2f charged twice within %d day(s)" % (vendor, amount, gap),
            )

order = {{"high": 0, "medium": 1, "low": 2}}
findings.sort(key=lambda f: (order.get(f["severity"], 9), -f["amount"]))
print("RESULT:" + json.dumps(findings))
'''

PROBE = '''import json
import os
import socket
import subprocess
import sys

out = {}

try:
    sock = socket.create_connection(("1.1.1.1", 80), timeout=3)
    sock.close()
    out["network_egress"] = "ALLOWED"
except Exception as exc:
    out["network_egress"] = "blocked: " + type(exc).__name__

try:
    with open("/etc/ledgerlock-probe", "w") as handle:
        handle.write("x")
    out["root_write"] = "ALLOWED"
except Exception as exc:
    out["root_write"] = "blocked: " + type(exc).__name__

try:
    with open("/tmp/ledgerlock-probe", "w") as handle:
        handle.write("x")
    out["tmp_write"] = "allowed"
except Exception as exc:
    out["tmp_write"] = "blocked: " + type(exc).__name__

out["secret_env_keys"] = sorted(
    key for key in os.environ if any(word in key.upper() for word in ("KEY", "TOKEN", "SECRET", "PASSWORD"))
)
out["uid"] = getattr(os, "getuid", lambda: None)()
out["cwd"] = os.getcwd()

children = []
try:
    for _ in range(100):
        children.append(subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.4)"]))
except Exception as exc:
    out["fork_error"] = type(exc).__name__
out["child_processes_started"] = len(children)
for child in children:
    try:
        child.kill()
    except Exception:
        pass

print("PROBE:" + json.dumps(out))
'''


def checker_script(rules: dict[str, Any]) -> str:
    compact = {
        "category_caps": rules["category_caps"],
        "meals_daily_cap": rules["meals_daily_cap"],
        "receipt_required_above": rules["receipt_required_above"],
        "approval_required_above": rules["approval_required_above"],
        "duplicate_window_days": rules["duplicate_window_days"],
    }
    return TEMPLATE.format(rules=json.dumps(compact))
