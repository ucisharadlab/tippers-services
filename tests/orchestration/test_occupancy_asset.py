from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

from dagster import RunConfig, materialize
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from datawhisk_shared.base import Base
from datawhisk_shared.orm import Occupancy
from orchestration.assets.occupancy import OccupancyTrainConfig, occupancy_model
from orchestration.resources import DataWhiskSessionResource


class _StubResource(DataWhiskSessionResource):
    database_url: str = "stub://unused"

    @contextmanager
    def session(self) -> Iterator[Session]:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[Occupancy.__table__])
        sm = sessionmaker(bind=engine)
        with sm() as s:
            now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
            for sid in (1, 42):
                s.add(Occupancy(
                    spaceid=sid,
                    starttime=now - timedelta(hours=1),
                    endtime=now,
                    occupancy=10,
                ))
            s.commit()
            yield s


def test_asset_materializes_with_default_config():
    result = materialize([occupancy_model], resources={"db": _StubResource()})
    assert result.success


def test_asset_materializes_with_custom_space_id():
    result = materialize(
        [occupancy_model],
        resources={"db": _StubResource()},
        run_config=RunConfig(
            ops={"occupancy_model": OccupancyTrainConfig(space_id=42, lookback_days=7)}
        ),
    )
    assert result.success
    mats = result.asset_materializations_for_node("occupancy_model")
    meta = mats[0].metadata
    assert meta["space_id"].value == 42
    assert meta["lookback_days"].value == 7
