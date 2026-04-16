from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from mlflow.exceptions import MlflowException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.deps import get_session
from api.main import app
from datawhisk_shared.base import Base
from datawhisk_shared.orm import Occupancy


@pytest.fixture
def sm(tmp_path):
    url = f"sqlite:///{tmp_path/'test.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine, tables=[Occupancy.__table__])
    with Session(engine) as s:
        s.add_all([
            Occupancy(spaceid=42, starttime=datetime(2026, 4, 14, 0), endtime=datetime(2026, 4, 14, 1), occupancy=10),
            Occupancy(spaceid=42, starttime=datetime(2026, 4, 14, 1), endtime=datetime(2026, 4, 14, 2), occupancy=20),
        ])
        s.commit()
    return sessionmaker(bind=engine)


@pytest.fixture
def client(sm):
    def _get_session():
        with sm() as s:
            yield s

    app.dependency_overrides[get_session] = _get_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_default_window_spans_last_observed(client):
    fake_model = MagicMock()
    fake_model.predict.return_value = [5.0] * 24
    with patch("api.routes.occupancy._resolver") as resolver:
        resolver.load.return_value = fake_model
        resolver.resolve_version.return_value = MagicMock(version=5)
        r = client.get("/services/occupancy/42")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["last_observed"].startswith("2026-04-14T02:00")
    assert len(body["history"]) == 2
    assert len(body["forecast"]) == 24
    assert body["model_version"] == "5"


def test_pure_history_when_end_before_last_observed(client):
    r = client.get(
        "/services/occupancy/42",
        params={"start": "2026-04-13T00:00:00Z", "end": "2026-04-14T00:00:00Z"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["forecast"]) == 0
    assert body["model_version"] is None


def test_pure_forecast_when_start_after_last_observed(client):
    fake_model = MagicMock()
    fake_model.predict.return_value = [9.0] * 3
    with patch("api.routes.occupancy._resolver") as resolver:
        resolver.load.return_value = fake_model
        resolver.resolve_version.return_value = MagicMock(version=1)
        r = client.get(
            "/services/occupancy/42",
            params={"start": "2026-04-15T00:00:00Z", "end": "2026-04-15T03:00:00Z"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["history"] == []
    assert len(body["forecast"]) == 3


def test_503_only_when_forecast_needed(client):
    with patch("api.routes.occupancy._resolver") as resolver:
        resolver.load.side_effect = MlflowException("no alias")
        r = client.get(
            "/services/occupancy/42",
            params={"start": "2026-04-15T00:00:00Z", "end": "2026-04-15T03:00:00Z"},
        )
    assert r.status_code == 503


def test_invalid_window(client):
    r = client.get(
        "/services/occupancy/42",
        params={"start": "2026-04-14T00:00:00Z", "end": "2026-04-10T00:00:00Z"},
    )
    assert r.status_code == 400


def test_non_integer_space_id(client):
    r = client.get("/services/occupancy/not-an-int")
    assert r.status_code == 422


def test_health():
    c = TestClient(app)
    assert c.get("/health").status_code == 200
