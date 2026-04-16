from __future__ import annotations

import io
from unittest.mock import patch

import joblib
from fastapi.testclient import TestClient

from api.main import app


def _joblib_bytes(obj) -> bytes:
    buf = io.BytesIO()
    joblib.dump(obj, buf)
    return buf.getvalue()


def test_upload_registers_per_space_model():
    with patch("api.routes.models.log_and_register_sklearn") as log_and_register:
        log_and_register.return_value = {
            "registered_model_name": "occupancy_space_42",
            "version": "1",
            "run_id": "run-xyz",
        }
        payload = _joblib_bytes({"weights": [1, 2, 3]})
        c = TestClient(app)
        r = c.post(
            "/admin/models/upload",
            data={"space_id": "42"},
            files={"file": ("model.joblib", payload, "application/octet-stream")},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["registered_model_name"] == "occupancy_space_42"
    assert body["version"] == "1"
    assert "alias" in body["note"].lower()
    kwargs = log_and_register.call_args.kwargs
    assert kwargs["space_id"] == 42
    assert kwargs["model_type"] == "occupancy"
    assert kwargs["extra_tags"]["uploaded_filename"] == "model.joblib"


def test_upload_supports_custom_model_type():
    with patch("api.routes.models.log_and_register_sklearn") as log_and_register:
        log_and_register.return_value = {
            "registered_model_name": "thermal_space_7",
            "version": "1",
            "run_id": "r",
        }
        c = TestClient(app)
        r = c.post(
            "/admin/models/upload",
            data={"space_id": "7", "category": "thermal"},
            files={"file": ("m.joblib", _joblib_bytes({}), "application/octet-stream")},
        )
    assert r.status_code == 200
    assert log_and_register.call_args.kwargs["model_type"] == "thermal"


def test_upload_rejects_non_joblib_payload():
    c = TestClient(app)
    r = c.post(
        "/admin/models/upload",
        data={"space_id": "42"},
        files={"file": ("garbage.bin", b"not a joblib file", "application/octet-stream")},
    )
    assert r.status_code == 400
    assert "could not load joblib" in r.json()["detail"]
