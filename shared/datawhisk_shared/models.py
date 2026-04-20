from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class OccupancyRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    spaceid: int
    starttime: datetime
    endtime: datetime
    occupancy: int

    @field_validator("starttime", "endtime", mode="after")
    @classmethod
    def _assume_utc(cls, v: datetime) -> datetime:
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v


class Space(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    space_id: int
    space_name: str
    parent_space_id: int | None = None
    coordinate_system_name: str | None = None
    space_shape: str | None = None
    extent: dict | list | None = None
    space_type_id: int | None = None
    gps_extent: dict | list | None = None
    radius: Decimal | None = None
    # coordinate[] arrives as a list of tuples/strings from psycopg; keep permissive.
    vertices: list[Any] | None = None
    gps_vertices: list[Any] | None = None


class Sensor(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sensor_id: str
    sensor_type: str | None = None
    space_id: int | None = None


class ThermometerObservation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sensor_id: str
    timestamp: datetime
    temperature: float

    @field_validator("timestamp", mode="after")
    @classmethod
    def _assume_utc(cls, v: datetime) -> datetime:
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v


class WemoObservation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sensor_id: str
    timestamp: datetime
    current_power: float

    @field_validator("timestamp", mode="after")
    @classmethod
    def _assume_utc(cls, v: datetime) -> datetime:
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v


class WiFiAPObservation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sensor_id: str
    timestamp: datetime
    client_count: int

    @field_validator("timestamp", mode="after")
    @classmethod
    def _assume_utc(cls, v: datetime) -> datetime:
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v