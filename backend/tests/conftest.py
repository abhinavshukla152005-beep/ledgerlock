import os
import sys
from pathlib import Path

os.environ.setdefault("SANDBOX_BACKEND", "local")
os.environ.setdefault("DB_PATH", "data/test-ledgerlock.db")
os.environ.setdefault("VULTR_INFERENCE_API_KEY", "")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
