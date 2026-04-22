"""End-to-end smoke test for the training pipeline.

Preconditions — the full docker compose stack must be up and `.env` configured
so that the Dagster asset can query the sensor DB for at least the target
space_id:

    docker compose up -d --build

Run this test explicitly (it's excluded from the default pytest run):

    pytest -m e2e

Override any of these with env vars if your stack isn't on the usual ports:

    E2E_API_URL          (default http://localhost:8000)
    E2E_DAGSTER_HOST     (default localhost)
    E2E_DAGSTER_PORT     (default 3000)
    E2E_SPACE_ID         (default 1)
    E2E_RUN_TIMEOUT_S    (default 120)
"""
from __future__ import annotations

import os
import time

import httpx
import pytest
from dagster import DagsterRunStatus
from dagster_graphql import DagsterGraphQLClient

API_URL = os.environ.get("E2E_API_URL", "http://localhost:8000")
DAGSTER_HOST = os.environ.get("E2E_DAGSTER_HOST", "localhost")
DAGSTER_PORT = int(os.environ.get("E2E_DAGSTER_PORT", "3000"))
SPACE_ID = int(os.environ.get("E2E_SPACE_ID", "1"))
RUN_TIMEOUT_S = float(os.environ.get("E2E_RUN_TIMEOUT_S", "120"))

_TERMINAL = {
    DagsterRunStatus.SUCCESS,
    DagsterRunStatus.FAILURE,
    DagsterRunStatus.CANCELED,
}


def _stack_reachable() -> bool:
    try:
        return httpx.get(f"{API_URL}/health", timeout=2.0).status_code == 200
    except Exception:
        return False


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not _stack_reachable(),
        reason=f"docker stack not reachable at {API_URL} — run `docker compose up -d`",
    ),
]


def _wait_for_run(run_id: str) -> DagsterRunStatus:
    client = DagsterGraphQLClient(hostname=DAGSTER_HOST, port_number=DAGSTER_PORT)
    deadline = time.monotonic() + RUN_TIMEOUT_S
    status: DagsterRunStatus | None = None
    while time.monotonic() < deadline:
        status = client.get_run_status(run_id)
        if status in _TERMINAL:
            return status
        time.sleep(1.5)
    pytest.fail(f"run {run_id} did not finish in {RUN_TIMEOUT_S}s (last status: {status})")


def test_train_triggers_run_and_updates_mapping():
    trigger = httpx.post(
        f"{API_URL}/train/{SPACE_ID}",
        params={"lookback_days": 1},
        timeout=10.0,
    )
    assert trigger.status_code == 200, trigger.text
    body = trigger.json()
    assert body["space_id"] == SPACE_ID
    assert body["job_name"] == "occupancy_training_job"
    run_id = body["run_id"]
    assert run_id

    status = _wait_for_run(run_id)
    assert status == DagsterRunStatus.SUCCESS, f"run finished as {status}"

    mapping = httpx.get(f"{API_URL}/services/mapping/{SPACE_ID}", timeout=10.0)
    assert mapping.status_code == 200, mapping.text
    row = mapping.json()
    assert row["space_id"] == SPACE_ID
    assert row["last_run_id"] == run_id
    assert row["occupancy_model_uri"] == f"models:/occupancy_space_{SPACE_ID}@production"
    assert row["last_trained"] is not None
