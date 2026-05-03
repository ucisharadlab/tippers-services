from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from datawhisk_shared import OccupancyRow


class ForecastInterval(BaseModel):
    starttime: datetime
    endtime: datetime
    predicted_occupancy: float


class OccupancyFeatures(BaseModel):
    space_id: int
    timestamp: datetime
    hour_of_day: int = Field(ge=0, le=23)
    day_of_week: int = Field(ge=0, le=6)
    is_weekend: bool
    lag_1h: float | None = None
    lag_24h: float | None = None


class OccupancyPrediction(BaseModel):
    space_id: int
    timestamp: datetime
    predicted_occupancy: float


class OccupancyResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    space_id: int
    start: datetime
    end: datetime
    last_observed: datetime
    history: list[OccupancyRow]
    forecast: list[ForecastInterval]
    model_version: str | None
    forecast_error: str | None = None


class PopularTimesResponse(BaseModel):
    space_id: int
    # days[0]=Monday … days[6]=Sunday; each inner list has 24 hourly averages (None = no data)
    days: list[list[float | None]]
