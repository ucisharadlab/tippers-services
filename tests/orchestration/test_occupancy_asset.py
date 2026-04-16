from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

from dagster import materialize
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from datawhisk_shared.base import Base
from datawhisk_shared.orm import Occupancy
from orchestration.assets.occupancy import occupancy_model
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
            s.add(Occupancy(
                spaceid=1,
                starttime=now - timedelta(hours=1),
                endtime=now,
                occupancy=10,
            ))
            s.commit()
            yield s


def test_asset_materializes():
    result = materialize([occupancy_model], resources={"db": _StubResource()})
    assert result.success
