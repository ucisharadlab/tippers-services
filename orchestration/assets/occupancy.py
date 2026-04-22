from datetime import datetime, timedelta, timezone

import dagster as dg
from sqlalchemy import select

from datawhisk_shared import OccupancyRow, upsert_model_mapping
from datawhisk_shared.orm import Occupancy
from orchestration.resources import DataWhiskSessionResource


class OccupancyTrainConfig(dg.Config):
    space_id: int = 1
    lookback_days: int = 30


@dg.asset(
    description="Occupancy model asset. Pulls training data; training + MLflow logging are Gabriel's placeholder.",
    group_name="occupancy",
)
def occupancy_model(
    context: dg.AssetExecutionContext,
    config: OccupancyTrainConfig,
    db: DataWhiskSessionResource,
) -> dg.MaterializeResult:
    end = datetime.now(tz=timezone.utc)
    start = end - timedelta(days=config.lookback_days)

    start_naive = start.astimezone(timezone.utc).replace(tzinfo=None)
    end_naive = end.astimezone(timezone.utc).replace(tzinfo=None)

    model_uri = f"models:/occupancy_space_{config.space_id}@production"

    with db.session() as session:
        orm_rows = session.scalars(
            select(Occupancy)
            .where(Occupancy.spaceid == config.space_id)
            .where(Occupancy.starttime >= start_naive)
            .where(Occupancy.starttime < end_naive)
            .order_by(Occupancy.starttime)
        ).all()
        rows = [OccupancyRow.model_validate(r) for r in orm_rows]

        context.log.info(f"pulled {len(rows)} rows for space_id={config.space_id}")

        # TODO(Gabriel): training logic goes here. When implemented:
        #     with mlflow.start_run() as run:
        #         mlflow.sklearn.log_model(sk_model=model, name="model",
        #                                   registered_model_name=...)

        upsert_model_mapping(
            session,
            space_id=config.space_id,
            last_run_id=context.run.run_id,
            occupancy_model_uri=model_uri,
            last_trained=end,
        )

    return dg.MaterializeResult(
        metadata={
            "rows": len(rows),
            "space_id": config.space_id,
            "lookback_days": config.lookback_days,
            "occupancy_model_uri": model_uri,
            "run_id": context.run.run_id,
            "training_status": "placeholder — no model produced",
        }
    )
