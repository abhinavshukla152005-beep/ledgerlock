from __future__ import annotations

import time
import uuid
from typing import Any

from . import codegen, engine, llm, policy, sandbox
from .config import settings


class Steps:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []
        self._started = time.monotonic()
        self._mark = self._started

    def add(self, name: str, status: str, detail: str) -> None:
        now = time.monotonic()
        self.items.append(
            {
                "name": name,
                "status": status,
                "detail": detail,
                "duration_ms": int((now - self._mark) * 1000),
            }
        )
        self._mark = now

    @property
    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self._started) * 1000)


def _canonical(findings: list[dict[str, Any]]) -> list[tuple]:
    return sorted(
        (
            f["rule"],
            f["severity"],
            tuple(f["txn_ids"]),
            round(float(f["amount"]), 2),
            f["message"],
        )
        for f in findings
    )


def _matches(result: Any, host_findings: list[dict[str, Any]]) -> bool:
    return (
        result.ok
        and result.payload is not None
        and _canonical(result.payload) == _canonical(host_findings)
    )


def _reason(result: Any) -> str:
    if result.error:
        return result.error
    if result.timed_out:
        return "sandbox timed out"
    if result.payload is None:
        return f"sandbox exit {result.exit_code}, no RESULT line"
    return "sandbox output diverged from the host reference"


def _feedback(result: Any) -> str:
    text = (result.stderr or "").strip() or (result.stdout or "").strip()
    return text[-900:] or _reason(result)


def _draft(rules: dict[str, Any], feedback: str | None = None) -> str | None:
    source = llm.draft_checker(rules, feedback)
    if not source:
        return None
    return None if codegen.validate(source) else source


def run_audit(expenses_text: str, policy_text: str) -> dict[str, Any]:
    run_id = uuid.uuid4().hex[:12]
    steps = Steps()
    base: dict[str, Any] = {
        "id": run_id,
        "status": "error",
        "verified": False,
        "findings": [],
        "quarantined": [],
        "steps": steps.items,
        "memo": "",
        "llm_source": None,
        "codegen_source": None,
        "policy_source": None,
        "currency": None,
        "row_count": 0,
        "quarantined_count": 0,
        "finding_count": 0,
        "containment": None,
        "backend": None,
        "duration_ms": 0,
        "error": None,
    }

    try:
        rows = engine.parse_rows(expenses_text)
    except (ValueError, KeyError) as exc:
        steps.add("ingest", "failed", str(exc))
        base["error"] = f"could not parse expenses: {exc}"
        base["duration_ms"] = steps.elapsed_ms
        return base
    steps.add("ingest", "ok", f"parsed {len(rows)} transactions from CSV")

    clean, quarantined = engine.split_quarantine(rows)
    base["quarantined"] = quarantined
    base["quarantined_count"] = len(quarantined)
    base["row_count"] = len(clean)
    if quarantined:
        ids = ", ".join(row["txn_id"] for row in quarantined)
        steps.add(
            "quarantine",
            "blocked",
            f"{len(quarantined)} row(s) held back before model or sandbox: {ids}",
        )
    else:
        steps.add("quarantine", "ok", "no instruction-like text in the ledger")

    rules, policy_source, llm_source = policy.load(policy_text)
    base["policy_source"] = policy_source
    base["llm_source"] = llm_source
    base["currency"] = rules["currency"]
    steps.add(
        "policy",
        "ok",
        f"rules resolved from {policy_source}"
        + (f" ({settings.inference_model})" if policy_source == "vultr-inference" else ""),
    )

    source = "template"
    script = codegen.checker_script(rules)
    if llm.available():
        drafted = _draft(rules)
        if drafted:
            script, source = drafted, "vultr-inference"
            steps.add(
                "codegen",
                "ok",
                f"checker drafted by {settings.inference_model}, accepted by the validator",
            )
        else:
            steps.add("codegen", "ok", "model draft rejected; deterministic checker used")
    else:
        steps.add(
            "codegen",
            "ok",
            f"deterministic checker for {len(rules['category_caps'])} categories, "
            f"{len(script.splitlines())} lines",
        )

    host_findings = engine.audit(clean, rules)
    result = sandbox.run(script, {"rows": clean})
    matches = _matches(result, host_findings)

    if not matches and source == "vultr-inference":
        steps.add("sandbox", "failed", _reason(result))
        redraft = _draft(rules, _feedback(result))
        if redraft:
            steps.add("retry", "ok", "model redrafted with the failure as feedback")
            script = redraft
            result = sandbox.run(script, {"rows": clean})
            matches = _matches(result, host_findings)
        else:
            steps.add("retry", "failed", "no usable redraft")

    if not matches and source == "vultr-inference":
        steps.add("fallback", "ok", "deterministic checker takes over")
        source = "template"
        script = codegen.checker_script(rules)
        result = sandbox.run(script, {"rows": clean})
        matches = _matches(result, host_findings)

    base["containment"] = result.containment
    base["backend"] = result.backend
    base["codegen_source"] = source

    if result.ok:
        steps.add(
            "sandbox",
            "ok",
            f"{result.backend} sandbox, exit {result.exit_code}, {result.duration_ms} ms",
        )
    else:
        steps.add("sandbox", "failed", _reason(result))

    if not matches:
        if result.ok:
            steps.add("verify", "failed", "sandbox output diverged from host reference")
        base.update(
            {
                "status": "unverified",
                "findings": host_findings,
                "finding_count": len(host_findings),
                "error": "sandbox output could not be verified against the host reference",
            }
        )
        _finish(base, steps, rules)
        return base

    steps.add(
        "verify",
        "ok",
        f"sandbox output matches host reference across {len(host_findings)} findings",
    )
    base["verified"] = True
    base["findings"] = result.payload
    base["finding_count"] = len(result.payload)
    base["status"] = "verified"
    _finish(base, steps, rules)
    return base


def _finish(run: dict[str, Any], steps: Steps, rules: dict[str, Any]) -> None:
    stats = {
        "row_count": run["row_count"],
        "quarantined_count": run["quarantined_count"],
        "currency": rules["currency"],
    }
    text, source = llm.memo(run["findings"], stats)
    run["memo"] = text
    run["llm_source"] = source
    steps.add(
        "memo",
        "ok",
        f"reviewer memo via {source}"
        + (f" ({settings.inference_model})" if source == "vultr-inference" else ""),
    )
    run["duration_ms"] = steps.elapsed_ms


def probe() -> dict[str, Any]:
    result = sandbox.run(codegen.PROBE, {}, marker="PROBE")
    payload = result.payload or {}
    return {
        "backend": result.backend,
        "containment": result.containment,
        "ok": result.ok,
        "timed_out": result.timed_out,
        "duration_ms": result.duration_ms,
        "payload": payload,
        "stderr": result.stderr.strip()[-400:],
        "error": result.error,
    }
