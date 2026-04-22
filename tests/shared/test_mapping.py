from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from datawhisk_shared import upsert_model_mapping
from datawhisk_shared.base import Base
from datawhisk_shared.orm import ModelSpaceMapping


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[ModelSpaceMapping.__table__])
    with Session(engine) as s:
        yield s


def test_upsert_inserts_new_row(session):
    row = upsert_model_mapping(
        session,
        space_id=1,
        last_run_id="run-1",
        occupancy_model_uri="models:/occupancy_space_1@production",
    )
    assert row.space_id == 1
    assert row.occupancy_model_uri == "models:/occupancy_space_1@production"
    assert row.thermal_model_uri is None
    assert row.last_run_id == "run-1"
    assert row.last_trained is not None


def test_upsert_updates_without_clobbering_sibling_uri(session):
    upsert_model_mapping(
        session,
        space_id=7,
        last_run_id="thermal-run",
        thermal_model_uri="models:/thermal_space_7@production",
    )
    upsert_model_mapping(
        session,
        space_id=7,
        last_run_id="occupancy-run",
        occupancy_model_uri="models:/occupancy_space_7@production",
    )

    row = session.get(ModelSpaceMapping, 7)
    assert row.thermal_model_uri == "models:/thermal_space_7@production"
    assert row.occupancy_model_uri == "models:/occupancy_space_7@production"
    assert row.last_run_id == "occupancy-run"


def test_upsert_honors_explicit_last_trained(session):
    fixed = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    row = upsert_model_mapping(
        session,
        space_id=3,
        last_run_id="run-x",
        last_trained=fixed,
    )
    # SQLite strips tzinfo on roundtrip; compare on the naive UTC value.
    assert row.last_trained.replace(tzinfo=timezone.utc) == fixed
