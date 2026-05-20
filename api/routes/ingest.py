from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import threading

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/ingest", tags=["ingest"])

_SCRIPT = pathlib.Path(__file__).parents[2] / "putting_into_occupancy.py"
_jobs: dict[int, dict] = {}


def _run(space_id: int) -> None:
    process = subprocess.Popen(
        [sys.executable, "-u", str(_SCRIPT)],
        env={**os.environ, "SPACE_ID": str(space_id)},
        cwd=str(_SCRIPT.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # merge stderr so all output appears together
        text=True,
    )
    for line in process.stdout:
        _jobs[space_id]["output"] += line
    process.wait()
    _jobs[space_id]["status"] = "done" if process.returncode == 0 else "error"


@router.post("/occupancy/{space_id}")
def start_ingest(space_id: int) -> dict:
    if _jobs.get(space_id, {}).get("status") == "running":
        raise HTTPException(status_code=409, detail="Ingestion already in progress for this space.")
    _jobs[space_id] = {"status": "running", "output": ""}
    threading.Thread(target=_run, args=(space_id,), daemon=True).start()
    return {"status": "started"}


@router.get("/occupancy/{space_id}/status")
def ingest_status(space_id: int) -> dict:
    return _jobs.get(space_id, {"status": "idle", "output": ""})
