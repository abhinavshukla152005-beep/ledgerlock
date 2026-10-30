from pathlib import Path

from app import agent, codegen, llm, policy

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


def _expenses() -> str:
    return (SAMPLES / "expenses.csv").read_text(encoding="utf-8")


def _policy() -> str:
    return (SAMPLES / "policy.yaml").read_text(encoding="utf-8")


EMPTY_DRAFT = "import json\n\n# returns nothing on purpose\nprint('RESULT:' + json.dumps([]))\n"


def _fake_memo(findings, stats):
    return "memo", "template"


def test_validator_blocks_dangerous_drafts():
    assert codegen.validate("import socket\nprint('RESULT:[]')") is not None
    assert codegen.validate("import subprocess as s\nprint('RESULT:[]')") is not None
    assert codegen.validate("print(eval('1'))\n# RESULT:") is not None
    assert codegen.validate("print('nothing')") is not None
    assert codegen.validate(EMPTY_DRAFT) is None


def test_model_retry_is_fed_the_failure(monkeypatch):
    rules, _, _ = policy.load(_policy())
    good = codegen.checker_script(rules)
    drafts = iter([EMPTY_DRAFT, good])
    seen_feedback: list[str | None] = []

    def fake_draft(rules, feedback=None):
        seen_feedback.append(feedback)
        return next(drafts)

    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "draft_checker", fake_draft)
    monkeypatch.setattr(llm, "memo", _fake_memo)

    run = agent.run_audit(_expenses(), _policy())

    assert run["status"] == "verified"
    assert run["verified"] is True
    assert run["codegen_source"] == "vultr-inference"
    assert run["finding_count"] == 9
    assert seen_feedback[0] is None
    assert seen_feedback[1]
    assert any(step["name"] == "retry" for step in run["steps"])


def test_bad_drafts_fall_back_to_template(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "draft_checker", lambda rules, feedback=None: EMPTY_DRAFT)
    monkeypatch.setattr(llm, "memo", _fake_memo)

    run = agent.run_audit(_expenses(), _policy())

    assert run["status"] == "verified"
    assert run["codegen_source"] == "template"
    names = [step["name"] for step in run["steps"]]
    assert "fallback" in names
    assert run["finding_count"] == 9
