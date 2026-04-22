import os

from dagster import Definitions, define_asset_job

from orchestration.assets import all_assets, occupancy_model
from orchestration.resources import DataWhiskSessionResource

occupancy_training_job = define_asset_job(
    name="occupancy_training_job",
    selection=[occupancy_model],
    description="Trains/refreshes the occupancy model for a single space_id (set via run config).",
)

defs = Definitions(
    assets=all_assets,
    jobs=[occupancy_training_job],
    resources={
        "db": DataWhiskSessionResource(database_url=os.environ["DATABASE_URL"]),
    },
)
