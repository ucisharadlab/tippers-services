from __future__ import annotations

from datetime import datetime, timedelta, timezone

import dagster as dg

from orchestration.resources import DataWhiskDBResource


@dg.asset(
    description="Occupancy model asset. Pulls training data; training + MLflow logging are Gabriel's placeholder.",
    group_name="occupancy",
)
def occupancy_model(context, db: DataWhiskDBResource) -> dg.MaterializeResult:
    end = datetime.now(tz=timezone.utc)
    start = end - timedelta(days=30)

    space_id = 1
    rows = db.get_client().pull_historical_occupancy(
        space_id=space_id, start_time=start, end_time=end
    )
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
