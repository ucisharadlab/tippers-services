from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.deps import get_session
from api.main import app
from datawhisk_shared.base import Base
from datawhisk_shared.orm import ModelSpaceMapping


@pytest.fixture
def client(tmp_path):
    url = f"sqlite:///{tmp_path/'mapping.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine, tables=[ModelSpaceMapping.__table__])
    with Session(engine) as s:
        s.add(ModelSpaceMapping(
            space_id=42,
            occupancy_model_uri="models:/occupancy_space_42@production",
            thermal_model_uri=None,
            last_trained=datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc),
            last_run_id="run-42",
        ))
        s.commit()
    sm = sessionmaker(bind=engine)

    def _get_session():
        with sm() as s:
            yield s

    app.dependency_overrides[get_session] = _get_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_get_mapping_hit(client):
    r = client.get("/services/mapping/42")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["space_id"] == 42
    assert body["occupancy_model_uri"] == "models:/occupancy_space_42@production"
    assert body["thermal_model_uri"] is None
    assert body["last_run_id"] == "run-42"
    assert body["last_trained"].startswith("2026-04-01T12:00")


def test_get_mapping_miss_is_404(client):
    r = client.get("/services/mapping/9999")
    assert r.status_code == 404


def test_get_mapping_rejects_non_integer_space_id(client):
    r = client.get("/services/mapping/not-an-int")
    assert r.status_code == 422
