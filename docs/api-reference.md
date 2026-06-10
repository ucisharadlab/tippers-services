# DataWhisk API Reference

Base URL (dev): `http://localhost:8000`

All endpoints are unauthenticated in Phase 1. Swagger UI is at `/docs`.

---

## Meta

### `GET /health`

Liveness probe. Always returns 200 — does **not** check DB or MLflow.

```json
{"status": "ok"}
```

### `GET /ready`

Readiness probe. Returns 200 if the external DB is reachable, 503 otherwise.

```json
{"status": "ready"}
```

Use for Docker/K8s readiness checks. Doesn't check MLflow (a missing model is "unready per-space", not "service down").

---

## Occupancy (`/services/occupancy`)

### `GET /services/occupancy/spaces`

Returns a list of space IDs that have occupancy data.

**Response (200):** `list[int]`

---

### `GET /services/occupancy/{space_id}`

Returns historical occupancy + model-based forecast for a space. The service automatically splits the requested window at the `last_observed` boundary (max `endtime` in the DB for that space).

#### Parameters

| Location | Name | Type | Required | Default | Notes |
|---|---|---|---|---|---|
| path | `space_id` | `int` | yes | — | Non-integer → 422 |
| query | `start` | ISO-8601 datetime | no | `last_observed - 24h` | Window start |
| query | `end` | ISO-8601 datetime | no | `last_observed + 24h` | Window end (may be in the future) |

If the space has no rows at all, `last_observed` falls back to `now(UTC)`.

#### Behavior

- **`[start, last_observed)`** → historical rows pulled from DB
- **`[last_observed, end)`** → forecast rows generated in 1h buckets via MLflow model
- If `end <= last_observed` → pure history, no model needed
- If `start >= last_observed` → pure forecast, no DB read for the gap

#### Response (200)

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
  "model_version": "5",
  "forecast_error": null
}
```

`model_version` is `null` when no forecast was generated (pure history request). `forecast_error` is non-null when the model ran but returned a partial or degraded result.

#### Error responses

| Status | Detail | Cause |
|---|---|---|
| 400 | `start must be before end` | Inverted window |
| 422 | field validation errors | Non-int `space_id`, malformed timestamp, trailing whitespace in param |
| 503 | `model not ready` | Forecast needed but no `@production` alias on `occupancy_space_{id}` |
| 500 | — | DB connection or SQL error (see `docker compose logs api`) |

#### Examples

```bash
# Default window (24h history + 24h forecast around last_observed)
curl 'http://localhost:8000/services/occupancy/42'

# Pure history
curl 'http://localhost:8000/services/occupancy/42?start=2024-04-01T00:00:00Z&end=2024-05-01T00:00:00Z'

# Pure forecast
curl 'http://localhost:8000/services/occupancy/42?start=2026-05-01T00:00:00Z&end=2026-05-02T00:00:00Z'
```

---

### `GET /services/occupancy/{space_id}/has-data`

Returns whether occupancy data exists for a space and how many rows there are.

#### Parameters

| Location | Name | Type | Required |
|---|---|---|---|
| path | `space_id` | `int` | yes |

#### Response (200)

```json
{"has_data": true, "row_count": 8760}
```

---

### `GET /services/occupancy/{space_id}/popular-times`

Returns a 7×24 matrix of average occupancy by day-of-week and hour, similar to Google Maps "popular times."

#### Parameters

| Location | Name | Type | Required |
|---|---|---|---|
| path | `space_id` | `int` | yes |

#### Response (200)

```json
{
  "space_id": 42,
  "days": [
    [0.0, 0.0, ..., 12.3],
    ...
  ]
}
```

`days` is a list of 7 lists (Monday=0 … Sunday=6), each containing 24 hourly average values. A value of `null` means no data for that slot.

---

## Spaces (`/services/spaces`)

### `GET /services/spaces/space-names`

Returns a mapping of space ID to human-readable space name.

**Response (200):** `dict[int, str]`

```json
{"42": "Bren Hall 1100", "7": "DBH 3011"}
```

---

### `GET /services/spaces/{space_id}/children`

Returns the child space IDs for a given parent space.

#### Parameters

| Location | Name | Type | Required |
|---|---|---|---|
| path | `space_id` | `int` | yes |

**Response (200):** `list[int]`

---

## Mapping (`/services/mapping`)

### `GET /services/mapping/{space_id}`

Returns the VAV zone mapping record for a space.

#### Parameters

| Location | Name | Type | Required |
|---|---|---|---|
| path | `space_id` | `int` | yes |

**Response (200):** `ModelSpaceMappingRow` — zone/space association record.

**Response (404):** Space not found in mapping table.

---

## Thermal (`/services/thermal`)

### `GET /services/thermal/zones`

Returns all available VAV zone IDs, sorted alphabetically.

**Response (200):** `list[str]`

---

### `GET /services/thermal/{zone_id}/coefficients`

Returns the regression coefficients for a zone's thermal model.

#### Parameters

| Location | Name | Type | Required |
|---|---|---|---|
| path | `zone_id` | `str` | yes |

#### Response (200)

```json
{"zone_id": "VAV-1-01", "alpha": 0.85, "beta": -0.12}
```

**Response (404):** Zone not found.

---

### `GET /services/thermal/{zone_id}/predict`

Returns a single-point thermal energy prediction for a zone.

#### Parameters

| Location | Name | Type | Required | Default | Notes |
|---|---|---|---|---|---|
| path | `zone_id` | `str` | yes | — | |
| query | `model_type` | `str` | no | `em` | `em` (Energy to Maintain), `etotal` (Total Energy), `ec` (Cooling Energy) |
| query | `granularity` | `str` | no | `local` | `local`, `global`, or `intermediate` |
| query | `zone_temp` | `float` | yes | — | Current zone temperature (°F) |
| query | `clg_setpoint` | `float` | yes | — | Cooling setpoint (°F) |
| query | `htg_setpoint` | `float` | no | — | Heating setpoint (°F) |
| query | `ambient_temp` | `float` | yes | — | Outdoor ambient temperature (°F) |
| query | `at` | ISO-8601 datetime | no | `now(UTC)` | Timestamp used to look up occupancy |

#### Response (200)

```json
{
  "zone_id": "VAV-1-01",
  "model_type": "em",
  "granularity": "local",
  "occupancy_used": 5.0,
  "occupancy_space_id": 42,
  "occupancy_fallback": false,
  "predicted_energy_kwh_per_min": 0.032,
  "ap_id_used": "AP-12",
  "model_version": null
}
```

`occupancy_fallback` is `true` when occupancy couldn't be resolved from the DB and a default was used. `ap_id_used` is only present when `granularity=intermediate`.

---

### `GET /services/thermal/{zone_id}/predict/range`

Returns thermal energy predictions at regular intervals over a time range.

#### Parameters

| Location | Name | Type | Required | Default | Notes |
|---|---|---|---|---|---|
| path | `zone_id` | `str` | yes | — | |
| query | `model_type` | `str` | no | `em` | `em`, `etotal`, or `ec` |
| query | `granularity` | `str` | no | `local` | `local`, `global`, or `intermediate` |
| query | `zone_temp` | `float` | yes | — | |
| query | `clg_setpoint` | `float` | yes | — | |
| query | `htg_setpoint` | `float` | no | — | |
| query | `ambient_temp` | `float` | yes | — | |
| query | `start` | ISO-8601 datetime | yes | — | Range start |
| query | `end` | ISO-8601 datetime | yes | — | Range end |
| query | `interval_minutes` | `int` | no | `60` | Must be ≥ 1 |

#### Response (200)

```json
[
  {
    "timestamp": "2026-06-03T08:00:00Z",
    "occupancy_used": 5.0,
    "occupancy_fallback": false,
    "predicted_energy_kwh_per_min": 0.032,
    "etotal_raw": 0.040,
    "em_raw": 0.028,
    "ap_id_used": "AP-12"
  }
]
```

`etotal_raw` and `em_raw` are only present when `model_type=ec`. `ap_id_used` is only present when `granularity=intermediate`.

---

### `GET /services/thermal/{zone_id}/optimize`

Runs the MILP HVAC scheduler for a single day. Returns an interval-by-interval schedule that minimizes energy cost subject to occupancy-driven comfort constraints.

#### Parameters

| Location | Name | Type | Required | Default | Notes |
|---|---|---|---|---|---|
| path | `zone_id` | `str` | yes | — | |
| query | `granularity` | `str` | no | `local` | `local`, `global`, or `intermediate` |
| query | `zone_temp` | `float` | yes | — | Starting zone temperature (°F) |
| query | `clg_setpoint` | `float` | yes | — | Cooling setpoint (°F) |
| query | `htg_setpoint` | `float` | no | — | Heating setpoint (°F) |
| query | `ambient_temp` | `float` | yes | — | Outdoor ambient temperature (°F) |
| query | `date` | ISO-8601 datetime | no | `today(UTC)` | Planning date |
| query | `interval_minutes` | `int` | no | `15` | Schedule resolution |

#### Response (200)

```json
{
  "zone_id": "VAV-1-01",
  "solver_status": "Optimal",
  "total_optimized_cost_usd": 1.42,
  "total_naive_cost_usd": 2.10,
  "savings_pct": 32.4,
  "interval_minutes": 15,
  "intervals": [
    {
      "timestamp": "2026-06-03T08:00:00Z",
      "state": "cooling",
      "temperature": 72.1,
      "naive_temperature": 74.5,
      "energy_kwh": 0.18,
      "interval_cost_usd": 0.024,
      "tou_price": 0.133,
      "occupancy": 5.0
    }
  ]
}
```

`state` is one of `cooling`, `maintaining`, or `off`.

---

### `GET /services/thermal/{zone_id}/optimize/range`

Runs the MILP optimizer over a multi-day date range.

#### Parameters

| Location | Name | Type | Required | Default | Notes |
|---|---|---|---|---|---|
| path | `zone_id` | `str` | yes | — | |
| query | `granularity` | `str` | no | `local` | |
| query | `zone_temp` | `float` | yes | — | |
| query | `clg_setpoint` | `float` | yes | — | |
| query | `htg_setpoint` | `float` | no | — | |
| query | `ambient_temp` | `float` | yes | — | |
| query | `start_date` | `YYYY-MM-DD` | yes | — | |
| query | `end_date` | `YYYY-MM-DD` | yes | — | Inclusive |
| query | `interval_minutes` | `int` | no | `15` | |

#### Response (200)

```json
{
  "zone_id": "VAV-1-01",
  "start_date": "2026-06-01",
  "end_date": "2026-06-03",
  "solver_status": "Optimal",
  "total_optimized_cost_usd": 4.21,
  "total_naive_cost_usd": 6.30,
  "savings_pct": 33.2,
  "interval_minutes": 15,
  "days": [
    {
      "date": "2026-06-01",
      "solver_status": "Optimal",
      "total_optimized_cost_usd": 1.40,
      "intervals": [...]
    }
  ]
}
```

`solver_status` at the top level is `Optimal` if all days solved optimally, `Partial` otherwise.

---

## Admin

### `POST /admin/models/upload`

Registers an externally-trained sklearn/joblib model in MLflow as a new version under the per-space registered model name. Promotion is **manual** — assign the `@production` alias in the MLflow UI.

#### Request

Content-type: `multipart/form-data`

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `space_id` | `int` | yes | — | Target space |
| `category` | `string` | no | `occupancy` | Model domain (`occupancy`, `thermal`, …) |
| `file` | file | yes | — | `.joblib`-serialized sklearn-compatible model |

#### Response (200)

```json
{
  "registered_model_name": "occupancy_space_42",
  "version": "3",
  "run_id": "b1f2...",
  "note": "Assign @production alias in MLflow UI to make this servable."
}
```

#### Error responses

| Status | Cause |
|---|---|
| 400 | File couldn't be loaded via `joblib.load` |
| 422 | Missing `space_id` or `file` |

#### Examples

```bash
curl -X POST http://localhost:8000/admin/models/upload \
     -F 'space_id=42' \
     -F 'file=@model.joblib'

curl -X POST http://localhost:8000/admin/models/upload \
     -F 'space_id=7' \
     -F 'category=thermal' \
     -F 'file=@thermal_model.joblib'
```

---

### `GET /admin/models/{space_id}/versions`

Lists all registered model versions for a space with their MLflow metadata.

#### Parameters

| Location | Name | Type | Required |
|---|---|---|---|
| path | `space_id` | `int` | yes |

#### Response (200)

```json
[
  {
    "version": "3",
    "is_production": true,
    "created_timestamp": 1717000000000,
    "run_id": "b1f2...",
    "rmse": 1.84,
    "mae": 1.21
  }
]
```

`rmse` and `mae` are `null` if the model was uploaded without metrics.

---

### `POST /admin/models/{space_id}/set-production`

Programmatically assigns the `@production` alias to a specific model version.

#### Parameters

| Location | Name | Type | Required | Notes |
|---|---|---|---|---|
| path | `space_id` | `int` | yes | |
| query | `version` | `str` | yes | Version number to promote |

#### Response (200)

```json
{
  "registered_model_name": "occupancy_space_42",
  "version": "3",
  "alias": "production"
}
```

**Response (400):** Version does not exist or alias assignment failed.

---

## Ingest (`/ingest`)

### `POST /ingest/occupancy/{space_id}`

Triggers a background ingest job for a space's occupancy data.

#### Parameters

| Location | Name | Type | Required |
|---|---|---|---|
| path | `space_id` | `int` | yes |

**Response (200):** `{"status": "started"}`

---

### `GET /ingest/occupancy/{space_id}/status`

Returns the current status of a running or completed ingest job.

#### Parameters

| Location | Name | Type | Required |
|---|---|---|---|
| path | `space_id` | `int` | yes |

#### Response (200)

```json
{"status": "running", "output": "...log lines..."}
```

`status` is one of `running`, `done`, `error`, or `idle`.

---

## Training (`/train`)

### `POST /train/{space_id}`

Starts a background training job for a space's occupancy model. On success, registers the trained model in MLflow; the `@production` alias must still be assigned manually.

#### Parameters

| Location | Name | Type | Required | Default | Notes |
|---|---|---|---|---|---|
| path | `space_id` | `int` | yes | — | |
| query | `lookback_days` | `int` | no | `30` | 1–365 |

#### Response (200)

```json
{
  "space_id": 42,
  "job_name": "train-42-20260603",
  "run_id": "c3d4..."
}
```

---

## Export (`/export`)

### `POST /export/occupancy/{space_id}`

Exports occupancy data for a space to a CSV file on the server.

#### Parameters

| Location | Name | Type | Required |
|---|---|---|---|
| path | `space_id` | `int` | yes |

#### Response (200)

```json
{"file": "occupancy_42_20260603.csv", "row_count": 8760}
```

---

## Multi-tenant MLflow routing

| Layer | File | Responsibility |
|---|---|---|
| Space model name | `api/mlflow_utils.py::model_name_for_space` | `space_id + category → "occupancy_space_42"` |
| Zone model name | `api/mlflow_utils.py::model_name_for_zone` | `zone_id + model_type + granularity → "{type}_{granularity}_{zone}"` |
| Logging | `api/mlflow_utils.py::log_and_register_sklearn` | Tags every run with `space_id` |
| Resolution | `api/mlflow_utils.py::ModelResolver` | `space_id → "models:/name@production" → loaded pyfunc` |
| Occupancy route | `api/routes/occupancy.py` | Calls resolver; returns 503 on `MlflowException` |
| Thermal route | `api/routes/thermal.py` | Zone-scoped model resolution |

Change the naming convention by subclassing `ModelResolver` and overriding `registered_name`. No other code needs to change.

---

## Swagger / OpenAPI

- Interactive docs: http://localhost:8000/docs
- Raw OpenAPI schema: http://localhost:8000/openapi.json
