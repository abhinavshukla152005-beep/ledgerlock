from pathlib import Path

from app import engine, policy

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


def load_rows():
    return engine.parse_rows((SAMPLES / "expenses.csv").read_text(encoding="utf-8"))


def test_csv_shape():
    rows = load_rows()
    assert len(rows) == 10
    assert rows[0]["txn_id"] == "TXN-1001"


def test_missing_column_is_rejected():
    try:
        engine.parse_rows("txn_id,date\n1,2026-10-01\n")
    except ValueError as exc:
        assert "missing columns" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_quarantine_holds_injection_row():
    clean, quarantined = engine.split_quarantine(load_rows())
    assert [row["txn_id"] for row in quarantined] == ["TXN-1009"]
    assert all(row["txn_id"] != "TXN-1009" for row in clean)
    assert quarantined[0]["matched_patterns"]


def test_findings_match_expected_rules():
    clean, _ = engine.split_quarantine(load_rows())
    rules, source, _ = policy.load((SAMPLES / "policy.yaml").read_text(encoding="utf-8"))
    assert source == "inline-yaml"

    findings = engine.audit(clean, rules)
    assert len(findings) == 9
    assert [f["rule"] for f in findings] == [
        "over_category_cap",
        "over_category_cap",
        "missing_approval",
        "over_category_cap",
        "over_category_cap",
        "suspected_duplicate",
        "over_category_cap",
        "missing_receipt",
        "meals_daily_cap",
    ]
    assert findings[0]["txn_ids"] == ["TXN-1003"]
    assert findings[5]["txn_ids"] == ["TXN-1007", "TXN-1008"]
    assert all(f["severity"] in {"high", "medium"} for f in findings)


def test_duplicate_outside_window_is_ignored():
    rows = [
        {
            "txn_id": "A",
            "date": "2026-10-01",
            "vendor": "Acme",
            "category": "software",
            "amount": 500.0,
            "currency": "INR",
            "receipt_attached": True,
            "approver": "",
            "note": "",
        },
        {
            "txn_id": "B",
            "date": "2026-10-20",
            "vendor": "Acme",
            "category": "software",
            "amount": 500.0,
            "currency": "INR",
            "receipt_attached": True,
            "approver": "",
            "note": "",
        },
    ]
    assert engine.audit(rows, engine.DEFAULT_RULES) == []
