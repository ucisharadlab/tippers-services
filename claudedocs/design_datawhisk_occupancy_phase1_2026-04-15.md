# DataWhisk Occupancy Service — Phase 1 Design Specification

**Date:** 2026-04-15
**Persona:** Senior Systems Architect
**Scope:** Project-level (monorepo — multi-service)
**Format:** Specification
**Inputs:** `claudedocs/research_datawhisk_stack_2026-04-15.md` (findings + locked Phase 1 Decisions)
**Status:** Design only — no implementation code produced (use `/sc:implement` next)

---

## 0. Design Premises (from locked Phase 1 Decisions)

| # | Decision |
|---|---|
| 1 | Manual model promotion via MLflow UI |
| 2 | Load-on-request; 503 when no `Production` model exists |
| 3 | External Postgres for `datawhisk`; local Postgres container for `dagster` + `mlflow` (2 DBs) |
| 4 | Local Docker volume for MLflow artifacts; `--serve-artifacts` on tracking server |
| 5 | In-process Dagster run launcher (simplified layout: webserver + daemon, no user-code container) |
| 6 | `occupancy_logs` is external-write; DataWhisk reads only |
| 7 | No authentication (dev / internal network only) |

All subsequent sections honor these decisions. Anything marked **[P2]** is deliberately deferred.

---

## 1. System Architecture

### 1.1 Context diagram (textual)

```
                         ┌─────────────────────────┐
                         │  External Sensor Writer │
                         │      (out of scope)     │
                         └────────────┬────────────┘
                                      │ writes occupancy_logs
                                      ▼
                         ┌─────────────────────────┐
                         │  Remote Postgres        │
                         │  (datawhisk DB)         │  ← external server
                         └────────────┬────────────┘
                                      │ read-only
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
              ▼                       ▼                       ▼
      ┌──────────────┐        ┌──────────────┐        ┌──────────────────┐
      │  FastAPI     │        │  Dagster     │        │  MLflow Tracking │
      │  :8000       │        │  webserver   │        │  :5000           │
      │              │        │  :3000       │◄──────►│  --serve-        │
      │              │        │  + daemon    │  log   │   artifacts      │
      └──────┬───────┘        └──────┬───────┘ model  └────────┬─────────┘
             │                       │                         │
             │ load Production       │ write runs/events       │ writes meta
             │ model (on request)    │                         │
             └───────────────────────┴─────┐         ┌─────────┘
                                           ▼         ▼
                                    ┌──────────────────────┐
                                    │  Local Postgres      │
                                    │  (dagster, mlflow)   │
                                    └──────────────────────┘

                                    ┌──────────────────────┐
                                    │  Docker volume:      │
                                    │  mlflow_artifacts    │
                                    └──────────────────────┘
```

### 1.2 Service inventory

| Service | Image / Base | Port | Purpose |
|---|---|---|---|
| `postgres` | `postgres:16` | 5432 (internal) | Dagster + MLflow metadata; two DBs created via init script |
| `mlflow` | `ghcr.io/mlflow/mlflow:v2.x` (or custom Dockerfile) | 5000 | Tracking server + registry; `--serve-artifacts` |
| `api` | custom (FastAPI) | 8000 | `GET /services/occupancy/{space_id}` |
| `dagster_webserver` | custom (Dagster) | 3000 | Dagster UI; loads assets in-process |
| `dagster_daemon` | same image as webserver | — | Schedules, sensors, run queue |

**Not in Phase 1:** separate user-code gRPC container, MinIO, Traefik, auth proxy.

### 1.3 Network topology

Single bridge network `datawhisk_net`. All services resolve each other by service name. Only `api` (8000), `dagster_webserver` (3000), and `mlflow` (5000) publish to host.

### 1.4 Data flow — forecast request

```
client ─GET /services/occupancy/{space_id}──► api
                                               │
                                               ├─► DataWhiskDB.pull_historical_occupancy(space_id, now-24h, now)
                                               │       └─► remote Postgres: SELECT from occupancy_logs
                                               │
                                               ├─► mlflow.pyfunc.load_model("models:/occupancy/Production")
                                               │       └─► MLflow tracking server → artifact volume
                                               │       (503 if no Production version exists)
                                               │
                                               ├─► model.predict(features_from_history)
                                               │
                                               └─► JSON: { history, forecast, model_version }
```

### 1.5 Data flow — model training

```
human/schedule ─materialize occupancy_model──► dagster_webserver
                                                 │
                                                 ├─► DataWhiskDBResource.get_client().pull_historical_occupancy(...)
                                                 │       └─► remote Postgres
                                                 │
                                                 ├─► train(df)   ← placeholder; Gabriel fills in
                                                 │
                                                 ├─► mlflow.sklearn.log_model(
                                                 │       model,
                                                 │       artifact_path="model",
                                                 │       registered_model_name="occupancy",
                                                 │   )
                                                 │       └─► MLflow tracking → artifact volume
                                                 │
                                                 └─► MaterializeResult(metadata={run_id, version, rows})

human ─► MLflow UI ─► transition version N → "Production"
```

---

## 2. Repository Layout

```
datawhisk/
├── docker-compose.yml
├── .env.example                       # checked in; .env is gitignored
├── .gitignore
├── README.md
├── pyproject.toml                     # root — dev deps (pytest, ruff, etc.)
│
├── shared/                            # framework-free package
│   ├── pyproject.toml                 # name: datawhisk-shared
│   └── datawhisk_shared/
│       ├── __init__.py
│       └── database.py                # DataWhiskDB class
│
├── api/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── main.py                        # FastAPI app, router registration
│   ├── deps.py                        # get_db, get_mlflow_client providers
│   ├── schemas.py                     # Pydantic response models
│   └── routes/
│       ├── __init__.py
│       ├── occupancy.py               # APIRouter(prefix="/services/occupancy")
│       └── thermal.py.future          # [P2] placeholder file, not imported
│
├── orchestration/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── workspace.yaml                 # points to definitions.py
│   ├── dagster.yaml                   # Postgres run/event/schedule storage
│   ├── definitions.py                 # Definitions(assets=[...], resources={...})
│   ├── resources.py                   # DataWhiskDBResource, MLflowResource wrapper
│   └── assets/
│       ├── __init__.py                # aggregates per-domain assets
│       ├── occupancy.py               # occupancy_model asset
│       └── thermal.py.future          # [P2] placeholder
│
├── infra/
│   ├── mlflow/
│   │   └── Dockerfile                 # mlflow + psycopg2 (custom image)
│   └── postgres/
│       └── init.sql                   # CREATE DATABASE dagster; CREATE DATABASE mlflow;
│
├── tests/
│   ├── shared/
│   │   └── test_database.py
│   ├── api/
│   │   └── test_occupancy_route.py
│   └── orchestration/
│       └── test_occupancy_asset.py
│
└── claudedocs/                        # existing
```

**Extensibility note for `thermal` (§5 requirement):** Adding the thermal service is three additive changes — no infra, no compose, no shared edits:
1. Rename `api/routes/thermal.py.future` → `thermal.py`; register router in `main.py`.
2. Rename `orchestration/assets/thermal.py.future` → `thermal.py`; add to `assets/__init__.py`.
3. Register `"thermal"` as a new MLflow model name (no code, just `mlflow.register_model` on first run).

---

## 3. Component Specifications

### 3.1 `shared/datawhisk_shared/database.py`

**Contract:** framework-free, imports only SQLAlchemy + pandas.

```python
class DataWhiskDB:
    def __init__(self, database_url: str) -> None: ...
    def pull_historical_occupancy(
        self,
        space_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> pd.DataFrame:
        """Returns DataFrame with columns: timestamp (tz-aware), space_id, occupancy."""
```

**Behavior:**
- Engine created once per instance (connection pool reuse).
- Query is parameterized (no f-string SQL).
- Returns empty DataFrame (not raises) when no rows — caller decides what 0-history means.
- Timestamps returned as UTC-aware.

**Dependencies:** `sqlalchemy>=2.0`, `psycopg2-binary`, `pandas`.
**Must NOT import:** `fastapi`, `dagster`, `mlflow`.

### 3.2 `api/deps.py`

```python
def get_db() -> DataWhiskDB:
    """App-level singleton (process-wide). Reuses SQLAlchemy engine pool."""

DBDep = Annotated[DataWhiskDB, Depends(get_db)]
```

Uses `functools.lru_cache` or a module-level instance to ensure one `DataWhiskDB` per process.

### 3.3 `api/routes/occupancy.py`

**Router:** `APIRouter(prefix="/services/occupancy", tags=["occupancy"])`

**Endpoint:**
```
GET /services/occupancy/{space_id}
Query params:
  - hours: int = 24   (how much history to return and feed to the model)
```

**Logic (per locked Decision #2 — load-on-request):**
```
1. now = datetime.utcnow()
2. start = now - timedelta(hours=hours)
3. history_df = db.pull_historical_occupancy(space_id, start, now)
4. try:
     model = mlflow.pyfunc.load_model("models:/occupancy/Production")
   except MlflowException as e:
     raise HTTPException(503, "model not ready")
5. forecast_df = model.predict(features(history_df))   # placeholder
6. return OccupancyResponse(
       space_id=space_id,
       history=history_df.to_dict(orient="records"),
       forecast=forecast_df.to_dict(orient="records"),
       model_version=<from model metadata>,
   )
```

**No in-memory cache in Phase 1** (per Decision #2 — revisit later).

### 3.4 `api/schemas.py`

```python
class OccupancyPoint(BaseModel):
    timestamp: datetime
    occupancy: int

class ForecastPoint(BaseModel):
    timestamp: datetime
    predicted_occupancy: float

class OccupancyResponse(BaseModel):
    space_id: str
    history: list[OccupancyPoint]
    forecast: list[ForecastPoint]
    model_version: str
```

### 3.5 `api/main.py`

- Creates FastAPI app (no lifespan model load per Decision #2).
- `app.include_router(occupancy.router)`
- Health endpoint: `GET /health` returns `{"status": "ok"}` — does NOT check MLflow (so liveness stays green when model unpromoted).
- Readiness endpoint: `GET /ready` returns 200 if DB reachable, 503 otherwise.

### 3.6 `orchestration/resources.py`

```python
class DataWhiskDBResource(ConfigurableResource):
    database_url: str
    def get_client(self) -> DataWhiskDB:
        return DataWhiskDB(self.database_url)
```

MLflow is configured via env var (`MLFLOW_TRACKING_URI`), not a Dagster resource — the raw `mlflow` client reads it automatically. Keeps the asset code identical to how a data scientist would write it in a notebook.

### 3.7 `orchestration/assets/occupancy.py`

```python
@dg.asset(
    description="Trains occupancy forecast model; logs to MLflow and registers a new version.",
    group_name="occupancy",
)
def occupancy_model(
    context: dg.AssetExecutionContext,
    db: DataWhiskDBResource,
) -> dg.MaterializeResult:
    end = datetime.utcnow()
    start = end - timedelta(days=30)   # training window; configurable later
    df = db.get_client().pull_historical_occupancy(space_id="*", start_time=start, end_time=end)

    model = train(df)   # placeholder — Gabriel fills in

    with mlflow.start_run() as run:
        mlflow.log_metric("rows", len(df))
        mlflow.log_param("training_window_days", 30)
        result = mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model",
            registered_model_name="occupancy",
        )

    return dg.MaterializeResult(metadata={
        "mlflow_run_id": run.info.run_id,
        "registered_model": "occupancy",
        "version": result.registered_model_version,
        "rows": len(df),
    })
```

**Note:** asset does NOT auto-promote (Decision #1 = manual).

### 3.8 `orchestration/definitions.py`

```python
defs = Definitions(
    assets=[occupancy_model],              # thermal appended here later
    resources={
        "db": DataWhiskDBResource(database_url=os.environ["DATABASE_URL"]),
    },
)
```

### 3.9 `orchestration/dagster.yaml`

Configures:
- `run_storage`, `event_log_storage`, `schedule_storage` → all Postgres-backed, pointing at the local `postgres` service, `dagster` database
- Run launcher: `DefaultRunLauncher` (in-process, Decision #5)

---

## 4. Infrastructure — `docker-compose.yml`

### 4.1 Services

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: dw
      POSTGRES_PASSWORD: dw
      POSTGRES_DB: postgres      # bootstrap only
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infra/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dw"]
      interval: 5s

  mlflow:
    build: ./infra/mlflow
    environment:
      MLFLOW_BACKEND_STORE_URI: postgresql://dw:dw@postgres:5432/mlflow
      MLFLOW_DEFAULT_ARTIFACT_ROOT: /mlartifacts
    command: >
      mlflow server
        --host 0.0.0.0 --port 5000
        --backend-store-uri $${MLFLOW_BACKEND_STORE_URI}
        --default-artifact-root $${MLFLOW_DEFAULT_ARTIFACT_ROOT}
        --serve-artifacts
    volumes:
      - mlflow_artifacts:/mlartifacts
    ports: ["5000:5000"]
    depends_on: { postgres: { condition: service_healthy } }

  api:
    build: ./api
    environment:
      DATABASE_URL: ${DATABASE_URL}               # external DataWhisk server
      MLFLOW_TRACKING_URI: http://mlflow:5000
    ports: ["8000:8000"]
    depends_on: { mlflow: { condition: service_started } }

  dagster_webserver:
    build: ./orchestration
    command: dagster-webserver -h 0.0.0.0 -p 3000 -w workspace.yaml
    environment:
      DAGSTER_HOME: /opt/dagster/dagster_home
      DATABASE_URL: ${DATABASE_URL}
      MLFLOW_TRACKING_URI: http://mlflow:5000
      DAGSTER_POSTGRES_USER: dw
      DAGSTER_POSTGRES_PASSWORD: dw
      DAGSTER_POSTGRES_DB: dagster
    volumes:
      - ./orchestration:/opt/dagster/app
      - dagster_home:/opt/dagster/dagster_home
    ports: ["3000:3000"]
    depends_on:
      postgres: { condition: service_healthy }
      mlflow:   { condition: service_started }

  dagster_daemon:
    build: ./orchestration
    command: dagster-daemon run
    environment: *dagster_env   # same as webserver via yaml anchor
    volumes:
      - ./orchestration:/opt/dagster/app
      - dagster_home:/opt/dagster/dagster_home
    depends_on:
      postgres: { condition: service_healthy }

volumes:
  postgres_data:
  mlflow_artifacts:
  dagster_home:
```

### 4.2 `.env.example`

```bash
# DataWhisk sensor data — external Postgres
DATABASE_URL=postgresql://USER:PASS@external-host:5432/datawhisk

# MLflow tracking (internal, resolved via docker DNS)
MLFLOW_TRACKING_URI=http://mlflow:5000

# Dagster (internal)
DAGSTER_HOME=/opt/dagster/dagster_home
```

**Note:** The requirements spec listed `MODEL_PATH=/app/models` — **removed** per MLflow decision.

### 4.3 `infra/postgres/init.sql`

```sql
CREATE DATABASE dagster;
CREATE DATABASE mlflow;
```

---

## 5. Contracts & Interfaces (Summary Table)

| Interface | Producer | Consumer | Contract |
|---|---|---|---|
| `occupancy_logs` table | External writer | `DataWhiskDB.pull_historical_occupancy` | schema owned externally; DataWhisk treats as read-only |
| `DataWhiskDB` class | `shared/` | FastAPI + Dagster | `pull_historical_occupancy(space_id, start, end) -> DataFrame` |
| MLflow registered model `occupancy` | Dagster `occupancy_model` asset | FastAPI `/services/occupancy` route | versioned; FastAPI reads `Production` stage only |
| `GET /services/occupancy/{space_id}` | FastAPI | External clients | JSON per §3.4 schema; 503 when model unpromoted |

---

## 6. Testing Strategy

### 6.1 Layering

| Layer | Framework | Scope | Runs where |
|---|---|---|---|
| `shared/` unit | pytest | `DataWhiskDB` against SQLite in-memory | `pytest tests/shared` |
| `shared/` integration | pytest + testcontainers | `DataWhiskDB` against real Postgres | CI (tagged `integration`) |
| `api/` unit | pytest + `TestClient` | Route logic with mocked DB + mocked MLflow | `pytest tests/api` |
| `orchestration/` unit | pytest + `dagster.materialize` | Asset runs with mocked `DataWhiskDBResource`, mocked `mlflow` | `pytest tests/orchestration` |
| End-to-end | pytest + docker-compose | Train → promote → serve → forecast | Manual / nightly |

### 6.2 Representative tests

**`tests/shared/test_database.py`**
- Given a seeded sensor table, `pull_historical_occupancy` returns DataFrame with correct rows, columns, ordering.
- Empty range returns empty DataFrame (not error).
- Timestamps are tz-aware UTC.
- SQL injection attempt via `space_id` is neutralized by parameterization.

**`tests/api/test_occupancy_route.py`**
- 200 path: mock DB returns 24 rows, mock MLflow returns dummy model → response matches `OccupancyResponse` schema.
- 503 path: mock MLflow raises `MlflowException("no Production version")` → route returns 503 with `detail="model not ready"`.
- DB error path: DB raises → 500 (not masked as 503).
- `hours` query param respected (DB called with correct window).
- `/health` always returns 200; `/ready` returns 503 when DB unreachable.

**`tests/orchestration/test_occupancy_asset.py`**
- `dagster.materialize([occupancy_model], resources={"db": StubDBResource(...)})` with MLflow patched:
  - Asset calls `pull_historical_occupancy` with a 30-day window.
  - Asset calls `mlflow.sklearn.log_model` with `registered_model_name="occupancy"`.
  - `MaterializeResult.metadata` contains `mlflow_run_id`, `version`, `rows`.
- Asset does NOT call `transition_model_version_stage` (manual promotion — Decision #1).
- Empty DataFrame from DB → asset logs warning, still produces a model (placeholder behavior; revisit).

### 6.3 Test doubles

- `StubDataWhiskDB` in `tests/shared/conftest.py` — returns canned DataFrames.
- `StubDBResource(ConfigurableResource)` — Dagster resource wrapper around the stub.
- MLflow mocked via `unittest.mock.patch("mlflow.sklearn.log_model")` and `patch("mlflow.pyfunc.load_model")` — no live MLflow in unit tests.

---

## 7. Non-Functional Requirements

| NFR | Phase 1 target | Notes |
|---|---|---|
| Forecast latency (p95) | < 2s | Dominated by `load_model` per-request (Decision #2); acceptable for dev |
| Training runtime | N/A (placeholder) | Real SLO once Gabriel's model lands |
| Availability | Best-effort (dev) | No redundancy, no HA |
| Security | Internal network only | No auth (Decision #7); document loudly in README |
| Observability | Dagster UI + FastAPI logs + MLflow UI | No centralized logging in Phase 1 |
| Backups | None | `mlflow_artifacts` volume is ephemeral for dev |

---

## 8. Known Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `load_model` on every request is slow | High | Medium | Accepted per Decision #2; add in-memory cache in P2 |
| No Production model on fresh deploy | High | Low | 503 by design; documented in README runbook |
| Remote DataWhisk Postgres unreachable | Medium | High | `/ready` returns 503; callers must retry |
| MLflow artifact volume fills disk | Medium | Medium | Manual volume prune for now; S3 migration in P2 |
| In-process Dagster runs block UI on heavy training | Low (placeholder model) | Medium | Revisit run launcher when real training lands |
| Someone deletes `mlflow_artifacts` volume | Medium | High (loss of all model history) | Document in README; don't use `docker compose down -v` |

---

## 9. Build Sequence (for `/sc:implement`)

Recommended order — each step independently testable:

1. **`shared/`** — `DataWhiskDB` class + unit tests. Foundation for both other services.
2. **`infra/postgres/init.sql`** + `docker-compose.yml` (postgres service only). Verify `dagster` + `mlflow` databases exist.
3. **`infra/mlflow/Dockerfile`** + mlflow service in compose. Verify UI at :5000, artifact upload via `mlflow` CLI.
4. **`orchestration/`** skeleton — `definitions.py`, `resources.py`, empty `occupancy_model` asset that logs a dummy model to MLflow. Verify materialize works; verify a version appears in MLflow registry.
5. **`api/`** — routes + schemas + `/health` + `/ready`. Without MLflow integration first (return stub response). Verify TestClient unit tests pass.
6. **Wire MLflow into `api/`** — add `mlflow.pyfunc.load_model` call + 503 fallback. Verify end-to-end: materialize in Dagster → promote in MLflow UI → hit FastAPI → get forecast.
7. **Full compose up** — all five services. Smoke test the golden path.
8. **README** — runbook: first-time bootstrap (materialize, promote, request), how to reset, troubleshooting.

---

## 10. Out of Scope for Phase 1 (Explicit)

- Thermal service (hooks provided via `.future` placeholders)
- User-code gRPC container for Dagster
- MinIO / S3 artifact store
- Authentication / authorization
- Ingestion of `occupancy_logs` (external)
- Auto-promotion / validation-gated promotion
- In-memory model caching in FastAPI
- Centralized logging / metrics / tracing
- CI/CD pipeline
- Production deployment topology

---

## 11. Next Step

Recommended command:

```
/sc:implement "DataWhisk Occupancy Service Phase 1 per claudedocs/design_datawhisk_occupancy_phase1_2026-04-15.md — build in the sequence in §9, generate tests per §6" --persona-architect --scope project --safe --c7 --with-tests
```

Key flags:
- `--safe` stops for confirmation on destructive infra steps (volumes, compose up).
- `--with-tests` produces test files alongside each component per §6.
- `--c7` keeps docs live for FastAPI / Dagster / MLflow API drift.

Implementation should NOT deviate from the locked Phase 1 Decisions in §0 without flagging first.
