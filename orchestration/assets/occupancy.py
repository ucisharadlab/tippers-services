from __future__ import annotations

from datetime import datetime, timedelta, timezone

import dagster as dg
from sqlalchemy import select

from datawhisk_shared import OccupancyRow
from datawhisk_shared.orm import Occupancy
from orchestration.resources import DataWhiskSessionResource


@dg.asset(
    description="Occupancy model asset. Pulls training data; training + MLflow logging are Gabriel's placeholder.",
    group_name="occupancy",
)
def occupancy_model(context, db: DataWhiskSessionResource) -> dg.MaterializeResult:
    end = datetime.now(tz=timezone.utc)
    start = end - timedelta(days=30)

    space_id = 1
    start_naive = start.astimezone(timezone.utc).replace(tzinfo=None)
    end_naive = end.astimezone(timezone.utc).replace(tzinfo=None)

    with db.session() as session:
        orm_rows = session.scalars(
            select(Occupancy)
            .where(Occupancy.spaceid == space_id)
            .where(Occupancy.starttime >= start_naive)
            .where(Occupancy.starttime < end_naive)
            .order_by(Occupancy.starttime)
        ).all()
        rows = [OccupancyRow.model_validate(r) for r in orm_rows]

    context.log.info(f"pulled {len(rows)} rows for space_id={space_id}")

    # TODO(Gabriel): training logic goes here. When implemented:
    #     with mlflow.start_run() as run:
    #         mlflow.sklearn.log_model(sk_model=model, name="model",
    #                                   registered_model_name=...)

    return dg.MaterializeResult(
        metadata={
            "rows": len(rows),
            "space_id": space_id,
            "training_status": "placeholder — no model produced",
        }
    )
