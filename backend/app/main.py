from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import agent, db, llm
from .config import settings

ROOT = Path(settings.app_root or Path(__file__).resolve().parents[2])
SAMPLES = ROOT / "samples"
MAX_UPLOAD = 512 * 1024

app = FastAPI(title="LedgerLock", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init_db()


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "sandbox_backend": settings.sandbox_backend,
        "containment": (
            "docker: no network, read-only root, cap-drop ALL, pids/mem/cpu caps"
            if settings.sandbox_backend == "docker"
            else "none (development fallback)"
        ),
        "inference": "vultr" if llm.available() else "unconfigured",
        "model": settings.inference_model,
    }


@app.get("/api/samples/expenses.csv", response_class=PlainTextResponse)
def sample_expenses() -> str:
    return (SAMPLES / "expenses.csv").read_text(encoding="utf-8")


@app.get("/api/samples/policy.yaml", response_class=PlainTextResponse)
def sample_policy() -> str:
    return (SAMPLES / "policy.yaml").read_text(encoding="utf-8")


@app.get("/api/samples/policy-brief.txt", response_class=PlainTextResponse)
def sample_brief() -> str:
    return (SAMPLES / "policy-brief.txt").read_text(encoding="utf-8")


@app.post("/api/audit")
async def audit(
    expenses: UploadFile = File(...),
    policy_text: str = Form(""),
) -> dict:
    raw = await expenses.read()
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="expenses file too large")
    try:
        expenses_text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="expenses must be UTF-8 CSV")

    run = agent.run_audit(expenses_text, policy_text)
    db.save_run(run)
    return run


@app.get("/api/runs")
def runs() -> list[dict]:
    return db.list_runs()


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict:
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@app.post("/api/containment/probe")
def containment_probe() -> dict:
    return agent.probe()


dist = ROOT / "frontend" / "dist"
if dist.is_dir():
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="ui")
