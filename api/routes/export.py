from __future__ import annotations

import os
import pathlib
import subprocess
import sys

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/export", tags=["export"])

_SCRIPT = pathlib.Path(__file__).parents[2] / "occupancy_data_for_spaceid.py"


@router.post("/occupancy/{space_id}")
def export_occupancy(space_id: int) -> dict:
    result = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        env={**os.environ, "SPACE_ID": str(space_id)},
        cwd=str(_SCRIPT.parent),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr.strip())
    row_count, output_file = result.stdout.strip().split("|")
    return {"file": output_file, "row_count": int(row_count)}
