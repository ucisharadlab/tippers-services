from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from datawhisk_shared import OccupancyRow


class ForecastInterval(BaseModel):
    starttime: datetime
    endtime: datetime
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
