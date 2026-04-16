import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for sub in ("shared", "api", "orchestration"):
    sys.path.insert(0, str(ROOT / sub))
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("MLFLOW_TRACKING_URI", "http://mlflow-test:5000")
