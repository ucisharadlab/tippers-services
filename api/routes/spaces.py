from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from api.deps import SessionDep
from datawhisk_shared.orm import Sensor, Space

router = APIRouter(prefix="/services/spaces", tags=["spaces"])


@router.get("/sensor-names", response_model=dict[int, str])
def get_sensor_names(session: SessionDep) -> dict[int, str]:
    rows = session.execute(
        select(Sensor.space_id, Sensor.sensor_name)
        .where(Sensor.space_id.isnot(None))
        .distinct(Sensor.space_id)
        .order_by(Sensor.space_id, Sensor.sensor_id)
    ).all()
    return {space_id: name for space_id, name in rows}


@router.get("/{space_id}/children", response_model=list[int])
def get_child_spaces(space_id: int, session: SessionDep) -> list[int]:
    return list(
        session.scalars(
            select(Space.space_id)
            .where(Space.parent_space_id == space_id)
            .order_by(Space.space_id)
        ).all()
    )
