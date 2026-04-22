from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app


def test_train_submits_run_with_config():
    with patch("api.routes.train.submit_occupancy_training") as submit:
        submit.return_value = "run-abc-123"
        r = TestClient(app).post("/train/42", params={"lookback_days": 7})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {
        "space_id": 42,
        "job_name": "occupancy_training_job",
        "run_id": "run-abc-123",
    }
    submit.assert_called_once_with(42, lookback_days=7)


def test_train_default_lookback():
    with patch("api.routes.train.submit_occupancy_training") as submit:
        submit.return_value = "run-xyz"
        r = TestClient(app).post("/train/7")

    assert r.status_code == 200
    submit.assert_called_once_with(7, lookback_days=30)


def test_train_propagates_client_failure_as_502():
    with patch("api.routes.train.submit_occupancy_training") as submit:
        submit.side_effect = RuntimeError("dagster unreachable")
        r = TestClient(app).post("/train/1")
    assert r.status_code == 502
    assert "dagster unreachable" in r.json()["detail"]


def test_train_rejects_non_integer_space_id():
    r = TestClient(app).post("/train/not-an-int")
    assert r.status_code == 422


def test_train_rejects_out_of_range_lookback():
    r = TestClient(app).post("/train/1", params={"lookback_days": 0})
    assert r.status_code == 422
