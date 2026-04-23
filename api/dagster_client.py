from __future__ import annotations

import os
from functools import lru_cache

from dagster_graphql import DagsterGraphQLClient


@lru_cache(maxsize=1)
def get_dagster_client() -> DagsterGraphQLClient:
    host = os.environ.get("DAGSTER_WEBSERVER_HOST", "dagster_webserver")
    port = int(os.environ.get("DAGSTER_WEBSERVER_PORT", "3000"))
    return DagsterGraphQLClient(hostname=host, port_number=port)


def submit_occupancy_training(space_id: int, lookback_days: int = 30) -> str:
    """Submit an `occupancy_training_job` run for a single space. Returns the Dagster run id."""
    client = get_dagster_client()
    run_config = {
        "ops": {
            "occupancy_model": {
                "config": {
                    "space_id": space_id,
                    "lookback_days": lookback_days,
                }
            }
        }
    }
    return client.submit_job_execution(
        job_name="occupancy_training_job",
        run_config=run_config,
        tags={"space_id": str(space_id), "triggered_by": "api"},
    )
