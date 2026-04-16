from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from mlflow.exceptions import MlflowException

from api.deps import DBDep
from api.mlflow_utils import ModelResolver
from api.schemas import ForecastInterval, OccupancyResponse

router = APIRouter(prefix="/services/occupancy", tags=["occupancy"])

_BUCKET = timedelta(hours=1)
_resolver = ModelResolver(model_type="occupancy", alias="production")


@router.get("/{space_id}", response_model=OccupancyResponse)
def get_occupancy(
    space_id: int,
    db: DBDep,
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
) -> OccupancyResponse:
    last_observed = db.get_latest_occupancy_end(space_id) or datetime.now(tz=timezone.utc)
    end = end or last_observed + timedelta(hours=24)
    start = start or last_observed - timedelta(hours=24)

    if start >= end:
        raise HTTPException(400, "start must be before end")

    # History: [start, min(end, last_observed))
    history = (
        db.pull_historical_occupancy(space_id, start, min(end, last_observed))
        if start < last_observed
        else []
    )

    # Forecast: [max(start, last_observed), end)
    forecast_start = max(start, last_observed)
    future: list[tuple[datetime, datetime]] = []
    t = forecast_start
    while t < end:
        future.append((t, min(t + _BUCKET, end)))
        t += _BUCKET

    forecast: list[ForecastInterval] = []
    model_version: str | None = None
    if future:
        try:
            model = _resolver.load(space_id)
        except MlflowException as e:
            raise HTTPException(503, "model not ready") from e
        predictions = model.predict([[i] for i in range(len(future))])
        forecast = [
            ForecastInterval(starttime=s, endtime=e, predicted_occupancy=float(p))
            for (s, e), p in zip(future, predictions)
        ]
        try:
            model_version = str(_resolver.resolve_version(space_id).version)
        except Exception:
            pass

    return OccupancyResponse(
        space_id=space_id,
        start=start,
        end=end,
        last_observed=last_observed,
        history=history,
        forecast=forecast,
        model_version=model_version,
    )
