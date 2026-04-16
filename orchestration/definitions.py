import os

from dagster import Definitions

from orchestration.assets import all_assets
from orchestration.resources import DataWhiskDBResource

defs = Definitions(
    assets=all_assets,
    resources={
        "db": DataWhiskDBResource(database_url=os.environ["DATABASE_URL"]),
    },
)
