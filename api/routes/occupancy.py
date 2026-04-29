from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from mlflow.exceptions import MlflowException
from sqlalchemy import func, select

from api.deps import SessionDep
from api.mlflow_utils import ModelResolver
from api.schemas import ForecastInterval, OccupancyResponse
from datawhisk_shared import OccupancyRow
from datawhisk_shared.orm import Occupancy

router = APIRouter(prefix="/services/occupancy", tags=["occupancy"])

_BUCKET = timedelta(hours=1)
_resolver = ModelResolver(model_type="occupancy", alias="production")


def _to_db(dt: datetime) -> datetime:
    """Tippers stores timestamps without tz; strip after normalizing to UTC."""
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


@router.get("/spaces", response_model=list[int])
def list_spaces(session: SessionDep) -> list[int]:
    return list(
        session.scalars(
            select(func.distinct(Occupancy.spaceid)).order_by(Occupancy.spaceid)
        ).all()
    )


@router.get("/{space_id}", response_model=OccupancyResponse)
def get_occupancy(
    space_id: int,
    session: SessionDep,
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
) -> OccupancyResponse:
    latest_raw = session.scalar(
        select(func.max(Occupancy.endtime)).where(Occupancy.spaceid == space_id)
    )
    if latest_raw is None:
        last_observed = datetime.now(tz=timezone.utc)
    else:
        last_observed = latest_raw.replace(tzinfo=timezone.utc)

    end = end or last_observed + timedelta(hours=24)
    start = start or last_observed - timedelta(hours=24)

    if start >= end:
        raise HTTPException(400, "start must be before end")

    history: list[OccupancyRow] = []
    if start < last_observed:
        history_end = min(end, last_observed)
        rows = session.scalars(
            select(Occupancy)
            .where(Occupancy.spaceid == space_id)
            .where(Occupancy.starttime >= _to_db(start))
            .where(Occupancy.starttime < _to_db(history_end))
            .order_by(Occupancy.starttime)
        ).all()
        history = [OccupancyRow.model_validate(r) for r in rows]

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
            model, version = _resolver.load(space_id)
        except MlflowException as e:
            if getattr(e, "error_code", "") == "RESOURCE_DOES_NOT_EXIST":
                raise HTTPException(404, f"no @production model for space {space_id}") from e
            raise HTTPException(503, "model not ready") from e
        predictions = model.predict([[i] for i in range(len(future))])
        forecast = [
            ForecastInterval(starttime=s, endtime=e, predicted_occupancy=float(p))
            for (s, e), p in zip(future, predictions)
        ]
        model_version = str(version.version)

    return OccupancyResponse(
        space_id=space_id,
        start=start,
        end=end,
        last_observed=last_observed,
        history=history,
        forecast=forecast,
        model_version=model_version,
    )
