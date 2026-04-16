from datetime import datetime

import pytest
from sqlalchemy import create_engine, text

from datawhisk_shared import DataWhiskDB, OccupancyRow, Space


@pytest.fixture
def sqlite_url(tmp_path) -> str:
    url = f"sqlite:///{tmp_path/'test.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE occupancy (
                spaceid   INTEGER   NOT NULL,
                starttime TIMESTAMP NOT NULL,
                endtime   TIMESTAMP NOT NULL,
                occupancy INTEGER   NOT NULL
            )
            """
        ))
        conn.execute(text(
            """
            CREATE TABLE space (
                space_id INTEGER PRIMARY KEY,
                space_name TEXT NOT NULL,
                parent_space_id INTEGER,
                coordinate_system_name TEXT,
                space_shape TEXT,
                extent TEXT,
                space_type_id INTEGER,
                gps_extent TEXT,
                radius NUMERIC
            )
            """
        ))
        conn.execute(text(
            "INSERT INTO occupancy VALUES "
            "(1, '2026-04-14 00:00:00', '2026-04-14 01:00:00', 10),"
            "(1, '2026-04-14 01:00:00', '2026-04-14 02:00:00', 15),"
            "(1, '2026-04-14 02:00:00', '2026-04-14 03:00:00', 20),"
            "(2, '2026-04-14 01:00:00', '2026-04-14 02:00:00', 99)"
        ))
        conn.execute(text(
            "INSERT INTO space (space_id, space_name, space_type_id) VALUES "
            "(1, 'Lobby', 5), (2, 'Cafe', 6)"
        ))
    return url


def test_pull_returns_pydantic_rows(sqlite_url):
    db = DataWhiskDB(sqlite_url)
    rows = db.pull_historical_occupancy(1, datetime(2026, 4, 14), datetime(2026, 4, 14, 3))
    assert len(rows) == 3
    assert all(isinstance(r, OccupancyRow) for r in rows)
    assert [r.occupancy for r in rows] == [10, 15, 20]


def test_pull_empty_window_returns_empty_list(sqlite_url):
    db = DataWhiskDB(sqlite_url)
    rows = db.pull_historical_occupancy(1, datetime(2030, 1, 1), datetime(2030, 1, 2))
    assert rows == []


def test_pull_filters_other_spaces(sqlite_url):
    db = DataWhiskDB(sqlite_url)
    rows = db.pull_historical_occupancy(1, datetime(2026, 4, 14), datetime(2026, 4, 14, 3))
    assert {r.spaceid for r in rows} == {1}


def test_get_latest_occupancy_end(sqlite_url):
    db = DataWhiskDB(sqlite_url)
    latest = db.get_latest_occupancy_end(1)
    assert latest == datetime(2026, 4, 14, 3)


def test_get_latest_occupancy_end_none_when_no_rows(sqlite_url):
    db = DataWhiskDB(sqlite_url)
    assert db.get_latest_occupancy_end(999) is None


def test_get_space_returns_pydantic_model(sqlite_url):
    db = DataWhiskDB(sqlite_url)
    space = db.get_space(1)
    assert isinstance(space, Space)
    assert space.space_name == "Lobby"
    assert space.space_type_id == 5


def test_get_space_returns_none_for_missing(sqlite_url):
    db = DataWhiskDB(sqlite_url)
    assert db.get_space(999) is None
