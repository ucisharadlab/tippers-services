from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from datawhisk_shared.models import OccupancyRow, Space


class DataWhiskDB:
    def __init__(self, database_url: str) -> None:
        self._engine: Engine = create_engine(database_url, pool_pre_ping=True)

    def pull_historical_occupancy(
        self,
        space_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> list[OccupancyRow]:
        query = text(
            """
            SELECT spaceid, starttime, endtime, occupancy
            FROM occupancy
            WHERE spaceid = :space_id
              AND starttime >= :start_time
              AND starttime <  :end_time
            ORDER BY starttime ASC
            """
        )
        with self._engine.connect() as conn:
            rows = conn.execute(
                query,
                {"space_id": space_id, "start_time": start_time, "end_time": end_time},
            ).mappings().all()
        return [OccupancyRow.model_validate(dict(r)) for r in rows]

    def get_latest_occupancy_end(self, space_id: int) -> datetime | None:
        """Most recent endtime for a space, or None if the space has no rows."""
        query = text(
            "SELECT MAX(endtime) AS latest FROM occupancy WHERE spaceid = :space_id"
        )
        with self._engine.connect() as conn:
            row = conn.execute(query, {"space_id": space_id}).mappings().first()
        if not row or not row["latest"]:
            return None
        latest = row["latest"]
        if not isinstance(latest, datetime):
            latest = datetime.fromisoformat(str(latest))
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        return latest

    def get_space(self, space_id: int) -> Space | None:
        query = text("SELECT * FROM space WHERE space_id = :space_id")
        with self._engine.connect() as conn:
            row = conn.execute(query, {"space_id": space_id}).mappings().first()
        return Space.model_validate(dict(row)) if row else None
