from pathlib import Path

from app import codegen, engine, policy, sandbox

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


def _clean_rows():
    rows = engine.parse_rows((SAMPLES / "expenses.csv").read_text(encoding="utf-8"))
    clean, _ = engine.split_quarantine(rows)
    return clean


def _rules():
    rules, _, _ = policy.load((SAMPLES / "policy.yaml").read_text(encoding="utf-8"))
    return rules


def test_sandboxed_checker_agrees_with_host_engine():
    rules = _rules()
    rows = _clean_rows()

    result = sandbox.run(codegen.checker_script(rules), {"rows": rows})

    assert result.ok, result.stderr
    assert result.payload is not None
    assert result.payload == engine.audit(rows, rules)


def test_probe_reports_environment_facts():
    result = sandbox.run(codegen.PROBE, {}, marker="PROBE")

    assert result.ok, result.stderr
    assert result.payload is not None
    assert "network_egress" in result.payload
    assert "uid" in result.payload
    assert isinstance(result.payload["secret_env_keys"], list)
