from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

import pytest
from dagster import RunConfig, materialize
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from datawhisk_shared.base import Base
from datawhisk_shared.orm import ModelSpaceMapping, Occupancy
from orchestration.assets.occupancy import OccupancyTrainConfig, occupancy_model
from orchestration.resources import DataWhiskSessionResource


class _FileResource(DataWhiskSessionResource):
    """Resource backed by a file-based SQLite DB. Dagster re-instantiates
    resources from config, so a shared file is the simplest way for the test
    to see what the asset wrote."""

    @contextmanager
    def session(self) -> Iterator[Session]:
        engine = create_engine(self.database_url)
        sm = sessionmaker(bind=engine)
        with sm() as s:
            yield s


@pytest.fixture
def db(tmp_path):
    url = f"sqlite:///{tmp_path/'asset.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(
        engine,
        tables=[Occupancy.__table__, ModelSpaceMapping.__table__],
    )
    with sessionmaker(bind=engine)() as s:
        now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        for sid in (1, 42):
            s.add(Occupancy(
                spaceid=sid,
                starttime=now - timedelta(hours=1),
                endtime=now,
                occupancy=10,
            ))
        s.commit()
    return _FileResource(database_url=url)


def test_asset_materializes_with_default_config(db):
    result = materialize([occupancy_model], resources={"db": db})
    assert result.success
    with db.session() as s:
        row = s.get(ModelSpaceMapping, 1)
        assert row is not None
        assert row.occupancy_model_uri == "models:/occupancy_space_1@production"
        assert row.last_run_id == result.run_id


def test_asset_materializes_with_custom_space_id(db):
    result = materialize(
        [occupancy_model],
        resources={"db": db},
        run_config=RunConfig(
            ops={"occupancy_model": OccupancyTrainConfig(space_id=42, lookback_days=7)}
        ),
    )
    assert result.success
    mats = result.asset_materializations_for_node("occupancy_model")
    meta = mats[0].metadata
    assert meta["space_id"].value == 42
    assert meta["lookback_days"].value == 7

    with db.session() as s:
        row = s.get(ModelSpaceMapping, 42)
        assert row is not None
        assert row.occupancy_model_uri == "models:/occupancy_space_42@production"
        assert row.last_run_id == result.run_id
        assert s.get(ModelSpaceMapping, 1) is None
