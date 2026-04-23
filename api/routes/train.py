from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.dagster_client import submit_occupancy_training

router = APIRouter(prefix="/train", tags=["train"])


class TrainResponse(BaseModel):
    space_id: int
    job_name: str
    run_id: str


@router.post("/{space_id}", response_model=TrainResponse)
def train_occupancy(
    space_id: int,
    lookback_days: int = Query(default=30, ge=1, le=365),
) -> TrainResponse:
    try:
        run_id = submit_occupancy_training(space_id, lookback_days=lookback_days)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"dagster submission failed: {e}") from e
    return TrainResponse(
        space_id=space_id,
        job_name="occupancy_training_job",
        run_id=run_id,
    )
