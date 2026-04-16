from __future__ import annotations

from datetime import datetime, timezone

from dagster import materialize

from datawhisk_shared import OccupancyRow
from orchestration.assets.occupancy import occupancy_model
from orchestration.resources import DataWhiskDBResource


class _StubClient:
    def pull_historical_occupancy(self, space_id, start_time, end_time):
        return [
            OccupancyRow(
                spaceid=space_id,
                starttime=datetime(2026, 4, 14, 0, tzinfo=timezone.utc),
                endtime=datetime(2026, 4, 14, 1, tzinfo=timezone.utc),
                occupancy=10,
            )
        ]


class _StubResource(DataWhiskDBResource):
    database_url: str = "stub://unused"

    def get_client(self):
        return _StubClient()


def test_asset_materializes():
    result = materialize([occupancy_model], resources={"db": _StubResource()})
    assert result.success
