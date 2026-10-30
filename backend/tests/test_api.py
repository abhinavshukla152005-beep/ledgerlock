from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
client = TestClient(app)


def test_health():
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["sandbox_backend"] == "local"
    assert body["inference"] == "unconfigured"


def test_audit_round_trip():
    csv_bytes = (SAMPLES / "expenses.csv").read_bytes()
    policy = (SAMPLES / "policy.yaml").read_text(encoding="utf-8")

    response = client.post(
        "/api/audit",
        files={"expenses": ("expenses.csv", csv_bytes, "text/csv")},
        data={"policy_text": policy},
    )
    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "verified"
    assert run["verified"] is True
    assert run["finding_count"] == 9
    assert run["quarantined_count"] == 1
    assert run["quarantined"][0]["txn_id"] == "TXN-1009"
    assert run["memo"]

    detail = client.get(f"/api/runs/{run['id']}").json()
    assert detail["finding_count"] == 9
    assert [step["name"] for step in detail["steps"]] == [
        "ingest",
        "quarantine",
        "policy",
        "codegen",
        "sandbox",
        "verify",
        "memo",
    ]


def test_bad_upload_is_rejected():
    response = client.post(
        "/api/audit",
        files={"expenses": ("expenses.csv", b"txn_id,date\n1,2026-10-01\n", "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "error"
