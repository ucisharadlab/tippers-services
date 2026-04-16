# DataWhisk API Reference

Base URL (dev): `http://localhost:8000`

All endpoints are unauthenticated in Phase 1. Swagger UI is at `/docs`.

---

## `GET /services/occupancy/{space_id}`

Returns historical occupancy + model-based forecast for a space. The service automatically splits the requested window at the `last_observed` boundary (max `endtime` in the DB for that space).

### Parameters

| Location | Name | Type | Required | Default | Notes |
|---|---|---|---|---|---|
| path | `space_id` | `int` | yes | — | Non-integer → 422 |
| query | `start` | ISO-8601 datetime | no | `last_observed - 24h` | Window start |
| query | `end` | ISO-8601 datetime | no | `last_observed + 24h` | Window end (may be in the future) |

If the space has no rows at all, `last_observed` falls back to `now(UTC)`.

### Behavior

- **`[start, last_observed)`** → historical rows pulled from DB
- **`[last_observed, end)`** → forecast rows generated in 1h buckets via MLflow model
- If `end <= last_observed` → pure history, no model needed
- If `start >= last_observed` → pure forecast, no DB read for the gap

### Response (200)

```json
{
  "space_id": 42,
  "start": "2026-04-13T02:00:00Z",
  "end": "2026-04-15T02:00:00Z",
  "last_observed": "2026-04-14T02:00:00Z",
  "history": [
    {"spaceid": 42, "starttime": "...", "endtime": "...", "occupancy": 10}
  ],
  "forecast": [
    {"starttime": "...", "endtime": "...", "predicted_occupancy": 12.5}
  ],
  "model_version": "5"
}
```

`model_version` is `null` when no forecast was generated (pure history request).

### Error responses

| Status | Detail | Cause |
|---|---|---|
| 400 | `start must be before end` | Inverted window |
| 422 | field validation errors | Non-int `space_id`, malformed timestamp, trailing whitespace in param |
| 503 | `model not ready` | Forecast needed but no `@production` alias on `occupancy_space_{id}` |
| 500 | — | DB connection or SQL error (see `docker compose logs api`) |

### Examples

**Default window (24h history + 24h forecast around `last_observed`):**
```bash
curl 'http://localhost:8000/services/occupancy/42'
```

**Pure history, past window:**
```bash
curl 'http://localhost:8000/services/occupancy/42?start=2024-04-01T00:00:00Z&end=2024-05-01T00:00:00Z'
```

**Pure forecast, future only:**
```bash
curl 'http://localhost:8000/services/occupancy/42?start=2026-05-01T00:00:00Z&end=2026-05-02T00:00:00Z'
```

---

## `POST /admin/models/upload`

Registers an externally-trained sklearn/joblib model in MLflow as a new version under the per-space registered model name. Promotion is **manual** — assign the `@production` alias in the MLflow UI.

### Request

Content-type: `multipart/form-data`

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `space_id` | int | yes | — | Target space |
| `category` | string | no | `occupancy` | Model domain (`occupancy`, `thermal`, ...) |
| `file` | file | yes | — | `.joblib`-serialized sklearn-compatible model |

### Response (200)

```json
{
  "registered_model_name": "occupancy_space_42",
  "version": "3",
  "run_id": "b1f2...",
  "note": "Assign @production alias in MLflow UI to make this servable."
}
```

### Error responses

| Status | Cause |
|---|---|
| 400 | File couldn't be loaded via `joblib.load` |
| 422 | Missing `space_id` or `file` |

### Examples

```bash
# Minimum upload
curl -X POST http://localhost:8000/admin/models/upload \
     -F 'space_id=42' \
     -F 'file=@model.joblib'

# With category (thermal service later)
curl -X POST http://localhost:8000/admin/models/upload \
     -F 'space_id=7' \
     -F 'category=thermal' \
     -F 'file=@thermal_model.joblib'
```

### What this endpoint does internally

1. Saves uploaded bytes to a temp file
2. `joblib.load(...)` — fails fast on corrupt files
3. Calls `log_and_register_sklearn(model, space_id, model_type=category)`:
   - Starts an MLflow run tagged with `space_id=<n>`
   - `mlflow.sklearn.log_model(name="model", registered_model_name="{category}_space_{space_id}")`
4. Returns new version number; deletes temp file

Uses `api/mlflow_utils.py::log_and_register_sklearn` — same utility any future training code should use.

---

## `GET /health`

Liveness probe. Always returns 200 — does **not** check DB or MLflow.

```json
{"status": "ok"}
```

Use for Docker/K8s liveness checks.

---

## `GET /ready`

Readiness probe. Returns 200 if the external DB is reachable, 503 otherwise.

```json
{"status": "ready"}
```

Use for Docker/K8s readiness checks. Doesn't check MLflow (a missing model is "unready per-space" not "service down").

---

## How the multi-tenant routing works

| Layer | File | Responsibility |
|---|---|---|
| Matching table | `api/mlflow_utils.py::model_name_for_space` | `space_id + category → "occupancy_space_42"` convention |
| Logging | `api/mlflow_utils.py::log_and_register_sklearn` | Ensures every run is tagged with `space_id` |
| Resolution | `api/mlflow_utils.py::ModelResolver` | `space_id → "models:/name@production" → loaded pyfunc` |
| Route | `api/routes/occupancy.py` | Calls resolver; returns 503 on `MlflowException` |

Change the convention by subclassing `ModelResolver` and overriding `registered_name`. No other code needs to change.

---

## Swagger / OpenAPI

- Interactive docs: http://localhost:8000/docs
- Raw OpenAPI schema: http://localhost:8000/openapi.json
