from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from mlflow.exceptions import MlflowException
from sqlalchemy import func, select

from api.deps import SessionDep
from api.mlflow_utils import ModelResolver
from api.schemas import ForecastInterval, OccupancyResponse, PopularTimesResponse
from datawhisk_shared import OccupancyRow
from datawhisk_shared.orm import Occupancy

log = logging.getLogger(__name__)

router = APIRouter(prefix="/services/occupancy", tags=["occupancy"])

_BUCKET = timedelta(hours=1)
_resolver = ModelResolver(model_type="occupancy", alias="production")


def _to_db(dt: datetime) -> datetime:
    """Tippers stores timestamps without tz; strip after normalizing to UTC."""
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


@router.get("/{space_id}/has-data")
def has_occupancy_data(space_id: int, session: SessionDep) -> dict:
    count = session.scalar(
        select(func.count()).where(Occupancy.spaceid == space_id)
    )
    return {"has_data": (count or 0) > 0, "row_count": count or 0}


@router.get("/spaces", response_model=list[int])
def list_spaces(session: SessionDep) -> list[int]:
    return list(
        session.scalars(
            select(func.distinct(Occupancy.spaceid)).order_by(Occupancy.spaceid)
        ).all()
    )


@router.get("/{space_id}/popular-times", response_model=PopularTimesResponse)
def get_popular_times(
    space_id: int,
    session: SessionDep,
) -> PopularTimesResponse:
    rows = session.scalars(
        select(Occupancy).where(Occupancy.spaceid == space_id)
    ).all()

    buckets: dict[int, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row.occupancy is not None:
            buckets[row.starttime.weekday()][row.starttime.hour].append(row.occupancy)

    days: list[list[float | None]] = []
    for dow in range(7):
        hours: list[float | None] = []
        for hr in range(24):
            vals = buckets[dow].get(hr)
            hours.append(round(sum(vals) / len(vals), 1) if vals else None)
        days.append(hours)

    return PopularTimesResponse(space_id=space_id, days=days)


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
    now = datetime.now(tz=timezone.utc)
    if latest_raw is None:
        last_observed = now
    else:
        # Cap at now: DB rows with future endtimes must not push forecast_start
        # past the user's end date, which would leave future empty.
        last_observed = min(latest_raw.replace(tzinfo=timezone.utc), now)

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
    forecast_error: str | None = None
    if future:
        try:
            model, version = _resolver.load(space_id)
            feature_df = pd.DataFrame(
                [
                    {
                        "hour": s.hour,
                        "dayofweek": s.weekday(),
                        "is_weekend": 1 if s.weekday() >= 5 else 0,
                    }
                    for s, _ in future
                ]
            )
            predictions = model.predict(feature_df)
            forecast = [
                ForecastInterval(starttime=s, endtime=e, predicted_occupancy=float(p))
                for (s, e), p in zip(future, predictions)
            ]
            model_version = str(version.version)
        except MlflowException as e:
            error_code = getattr(e, "error_code", "")
            if error_code in ("RESOURCE_DOES_NOT_EXIST", "INVALID_PARAMETER_VALUE"):
                forecast_error = (
                    f"No production model for space {space_id} — "
                    "train one via Dagster and assign the @production alias in MLflow."
                )
            else:
                log.exception("MLflow error loading model for space %s", space_id)
                forecast_error = "Model service unavailable — forecast could not be generated."
        except Exception as exc:
            log.exception("Prediction error for space %s", space_id)
            forecast_error = f"Forecast could not be generated — {type(exc).__name__}: {exc}"

    return OccupancyResponse(
        space_id=space_id,
        start=start,
        end=end,
        last_observed=last_observed,
        history=history,
        forecast=forecast,
        model_version=model_version,
        forecast_error=forecast_error,
    )
