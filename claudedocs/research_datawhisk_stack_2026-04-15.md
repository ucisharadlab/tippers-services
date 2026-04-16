# DataWhisk Stack Research Report

**Date:** 2026-04-15
**Scope:** FastAPI + Dagster + Postgres monorepo patterns, **MLflow model registry** for ML artifacts, Software-Defined Assets (SDAs) as MLflow producers
**Depth:** Deep (3–4 hop, multi-source)
**Status:** Research only — no implementation performed (per `/sc:research` boundaries)
**Revision:** Updated to replace shared-volume model exchange with MLflow model registry (recommended by user during review).

---

## Executive Summary

The DataWhisk requirements map cleanly onto documented, production-grade patterns. **Key revision from original spec:** replace the shared Docker volume for model artifacts with an **MLflow tracking server + model registry**. This adds one service but eliminates custom versioning, gives a UI for run comparison, and decouples FastAPI from Dagster's filesystem.

The main architectural decisions are:

1. **Model artifact exchange** should use **MLflow**, not a shared Docker volume. Dagster trains and calls `mlflow.sklearn.log_model(...)`; FastAPI loads via `mlflow.pyfunc.load_model("models:/occupancy/Production")`. Versioning, stage promotion (Staging→Production), metric logging, and lineage are built in. Dagster has a first-class `dagster-mlflow` integration. The `/app/models` shared volume is removed.
2. **Database access** should live in a `shared/` package imported by both FastAPI and Dagster, wrapped as a **Dagster `ConfigurableResource`** on the orchestrator side and as a **FastAPI `Depends()` provider** on the API side. Same class, two injection shells. This is the canonical pattern in Dagster's DuckDB/Postgres integrations.
3. **Dagster OSS deployment** requires *four* services, not two: webserver, daemon, **user-code gRPC container (port 4000)**, and Postgres. The requirements spec lists only webserver+daemon; omitting the user-code container works for a `dagster dev` local setup but is non-standard for `docker compose` and will require revisiting before production.
4. **FastAPI model loading** should use the `lifespan` async context manager (not the deprecated `@app.on_event("startup")`) so `joblib.load()` runs once at boot and the model is held in a module-level dict.
5. **Extensibility for the `thermal` service** is best served by an `APIRouter`-per-domain layout on the FastAPI side and one Dagster `Definitions` object that merges per-domain asset modules. Adding thermal = new file in `api/routes/`, new asset in `orchestration/assets/`, and a new registered model name in MLflow (e.g., `models:/thermal/Production`). No infra changes.

---

## 1. Monorepo Layout Patterns

### Finding
Across FastAPI+Dagster reference projects, the dominant layout is **domain-sliced, not layer-sliced**. Each service (FastAPI, Dagster) gets its own top-level directory with its own Dockerfile, and a sibling `shared/` package holds cross-service utilities that are pip-installable (editable) into both container images.

### Recommended structure (for DataWhisk)
```
datawhisk/
├── docker-compose.yml           # postgres, mlflow, api, dagster-webserver, dagster-daemon
├── .env                         # incl. MLFLOW_TRACKING_URI=http://mlflow:5000
├── shared/                      # pip install -e . into both images
│   ├── pyproject.toml
│   └── datawhisk_shared/
│       ├── __init__.py
│       └── database.py          # DataWhiskDB class
├── api/                         # FastAPI service
│   ├── Dockerfile
│   ├── main.py                  # lifespan loads from MLflow registry
│   └── routes/
│       ├── occupancy.py
│       └── thermal.py           # (future, no infra change)
├── orchestration/               # Dagster code location
│   ├── Dockerfile
│   ├── workspace.yaml
│   ├── dagster.yaml
│   └── assets/
│       ├── __init__.py          # Definitions()
│       ├── occupancy.py         # logs + registers model to MLflow
│       └── thermal.py           # (future)
├── mlflow/                      # (optional) custom Dockerfile if not using official image
└── claudedocs/
```

### Why this works for extensibility
Adding `thermal` is purely additive: one new file under `api/routes/`, one new `@asset` under `orchestration/assets/`. Neither the compose file nor the shared DB utility changes. This is the explicit design goal stated in the requirements (§5).

### Confidence: High
Matches the Full-Stack FastAPI Template and the Dagster OSS docker reference deployment.

---

## 2. Model Artifact Exchange — MLflow Model Registry

### Finding (revised)
The original spec proposed a shared Docker volume (`model_store` at `/app/models`) as the model-exchange mechanism between Dagster and FastAPI. **Recommendation: replace this with MLflow.** A shared volume works for a single-model MVP but forces you to hand-roll everything a model registry provides for free: versioning, stage promotion, metric tracking, rollback, and UI.

### Architecture with MLflow
- **MLflow Tracking Server** — new service in `docker-compose.yml`, port 5000. Uses the existing `postgres` service (new database `mlflow`) as its metadata backend and a local mounted dir (or S3 later) as artifact store.
- **Dagster asset (producer):** uses `dagster-mlflow` resource or direct `mlflow` client to `mlflow.sklearn.log_model(model, artifact_path="model", registered_model_name="occupancy")`. Each materialization creates a new registered version.
- **FastAPI (consumer):** lifespan calls `mlflow.pyfunc.load_model("models:/occupancy/Production")`. Stage-based URIs mean promoting a new version doesn't require a code change.
- **Model promotion:** done via MLflow UI or API (`client.transition_model_version_stage(...)`). Dagster can auto-promote after validation passes, or leave it manual for human approval.

### What goes away vs. what's added
| Removed | Added |
|---|---|
| `model_store` named volume | `mlflow` service in docker-compose |
| `MODEL_PATH` env var | `MLFLOW_TRACKING_URI=http://mlflow:5000` env var |
| Custom atomic-write logic | (MLflow handles artifact finalization) |
| Custom versioning scheme | MLflow registered-model versions + stages |
| `joblib.dump` / `joblib.load` calls | `mlflow.<flavor>.log_model` / `mlflow.pyfunc.load_model` |

### Why not IO managers either
Same logic as before: IO managers are for Dagster-internal producer/consumer pairs. Here, MLflow is the durable store *and* the cross-service protocol. No IO manager needed.

### Gotchas
- **MLflow tracking server needs Postgres backend + artifact store configured at startup.** The default "local files" mode won't work across containers.
- **Artifact store path must be network-reachable from the FastAPI container** when it downloads the model. If you use a local-dir artifact store, mount it into both MLflow and FastAPI, OR use `mlflow server --serve-artifacts` so FastAPI fetches via HTTP (simpler, recommended).
- **Cold-start still applies:** if no model has been promoted to Production yet, `load_model` raises. Handle in lifespan with a fallback to 503.

### Confidence: High (MLflow is the standard; `dagster-mlflow` is first-party)

---

## 3. Software-Defined Assets for ML Artifacts

### Finding
A Dagster asset that produces an ML model and logs it to MLflow is a documented, standard pattern. The canonical shape (with MLflow):

```python
# illustrative, not for direct use — see /sc:design for actual design
import mlflow

@dg.asset
def occupancy_model(db: DataWhiskDBResource) -> dg.MaterializeResult:
    df = db.get_client().pull_historical_occupancy(...)
    model = train(df)                         # Gabriel's placeholder
    with mlflow.start_run() as run:
        mlflow.log_metric("rows", len(df))
        mlflow.sklearn.log_model(
            model,
            artifact_path="model",
            registered_model_name="occupancy",
        )
    return dg.MaterializeResult(metadata={
        "mlflow_run_id": run.info.run_id,
        "registered_model": "occupancy",
        "rows": len(df),
    })
```

Key points:
- **Resources** inject the DB (`db: DataWhiskDBResource`). Same `DataWhiskDB` class FastAPI uses, wrapped as a Dagster `ConfigurableResource`.
- **`dagster-mlflow` integration** provides an `mlflow_tracking` resource that auto-wires the tracking URI and tags runs with Dagster run IDs — worth adopting over raw `mlflow` calls.
- `MaterializeResult` surfaces the MLflow run ID in the Dagster UI for click-through debugging.

### Promotion strategy (open question for design)
Three options:
1. **Manual:** Dagster registers new versions; humans promote in MLflow UI. Safest, slowest.
2. **Auto-promote on materialize:** Dagster transitions the new version to `Production` immediately. Fast, risky.
3. **Validation asset:** `occupancy_model` produces the version; a downstream `occupancy_model_validated` asset runs checks and promotes if they pass. Recommended.

### Gotcha
The user-code (or webserver/daemon in the simplified layout) container must have `MLFLOW_TRACKING_URI` set and `mlflow` + training libs (`scikit-learn`, etc.) installed. FastAPI only needs `mlflow` + the model's runtime deps — not the training libs.

### Confidence: High

---

## 4. FastAPI Patterns — Lifespan + Router + DI

### Finding
Three patterns, all documented in current FastAPI docs:

**(a) Lifespan for model loading** — replaces the deprecated `@app.on_event("startup")`. With MLflow:
```python
import mlflow.pyfunc

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ml_models["occupancy"] = mlflow.pyfunc.load_model("models:/occupancy/Production")
    except mlflow.exceptions.MlflowException:
        ml_models["occupancy"] = None  # route returns 503 until promoted
    yield
    ml_models.clear()
```

**(b) `APIRouter` per domain** — clean prefix, clean tags, ready for the thermal addition:
```python
router = APIRouter(prefix="/services/occupancy", tags=["occupancy"])
# in main.py: app.include_router(occupancy.router)
```

**(c) `Depends()` for the shared DB** — mirrors the Dagster resource injection, same class:
```python
def get_db() -> DataWhiskDB: ...
DBDep = Annotated[DataWhiskDB, Depends(get_db)]

@router.get("/{space_id}")
def forecast(space_id: str, db: DBDep): ...
```

### Gotcha
If no model version has been promoted to `Production` in MLflow yet, `load_model` raises. Handle in lifespan (catch, set `None`, return 503 from route), or add a one-time bootstrap step that trains+promotes before FastAPI starts. Healthcheck on `depends_on` can gate this.

Also: if MLflow is unreachable at FastAPI boot, lifespan hangs. Set a client timeout and degrade gracefully.

### Confidence: High

---

## 5. Dagster docker-compose — What The Spec Misses

### Finding
Per the Dagster OSS deployment guide, a correct compose file has **four** services, not two:

1. `postgres` — run/event/schedule storage (distinct from the app's sensor-data Postgres, though they *can* share an instance with separate databases)
2. `user_code` — gRPC server on **port 4000**, loads assets, owns the ML training deps
3. `webserver` — port 3000, UI, talks to user_code via gRPC
4. `daemon` — schedules, sensors, run queue; talks to user_code via gRPC

Additional requirements:
- `DAGSTER_HOME=/opt/dagster/dagster_home/` (or the spec's `/app/dagster_home`)
- `DAGSTER_POSTGRES_USER`, `DAGSTER_POSTGRES_PASSWORD`, `DAGSTER_POSTGRES_DB` — used by `dagster.yaml` to configure run/event storage
- `DAGSTER_CURRENT_IMAGE` on the user_code service — needed if you use `DockerRunLauncher` for isolated runs
- Docker socket mount (`/var/run/docker.sock`) if using Docker run launcher
- Bridge network so webserver/daemon can resolve `user_code:4000`

### Risk
The spec's two-service Dagster model ("webserver and daemon") is viable for MVP using `dagster dev`-style workspaces (webserver hosts user code in-process), but this is not the production path. For a *single-code-location, single-container* setup, you can run webserver with an in-process `workspace.yaml` pointing at `orchestration/assets`, and the daemon can share the same image. This is simpler and is probably what the spec intends — but call it out.

### Confidence: High

---

## 6. Shared Database Utility — Dual-Consumer Pattern

### Finding
`shared/datawhisk_shared/database.py` should export a plain class, then adapt to each framework:

- **FastAPI:** wrap in a `Depends()` provider; instance lifetime = request (or app-level singleton for connection pooling).
- **Dagster:** wrap in a `ConfigurableResource` subclass; Dagster manages lifecycle.

This avoids the anti-pattern of importing the FastAPI `Depends` object (or Dagster types) into shared code — `shared/` should depend only on SQLAlchemy + pandas.

### Pattern sketch
```python
# shared/datawhisk_shared/database.py — framework-free
class DataWhiskDB:
    def __init__(self, url: str): self.engine = create_engine(url)
    def pull_historical_occupancy(self, space_id, start_time, end_time) -> pd.DataFrame: ...
```
Then:
- `api/deps.py` — `def get_db() -> DataWhiskDB`
- `orchestration/resources.py` — `class DataWhiskDBResource(ConfigurableResource): url: str; def get_client(self) -> DataWhiskDB`

### Confidence: High

---

## 7. Open Questions for Design Phase

1. **Model promotion strategy** — manual, auto, or validation-gated? (Recommend validation-gated.)
2. **Cold-start behavior** — what does `/services/occupancy/{space_id}` return when no `Production` model exists?
3. **Postgres instance topology** — one instance with three databases (`datawhisk`, `dagster`, `mlflow`) or separate instances? (Recommend one instance, three databases for Phase 1.)
4. **MLflow artifact store** — local mounted dir via `--serve-artifacts`, or S3/MinIO? (Recommend `--serve-artifacts` for MVP, S3 later.)
5. **Run launcher** — in-process, Docker run launcher, or K8s? (Recommend in-process for Phase 1.)
6. **Sensor data ingestion path** — who writes to `occupancy_logs`? Upstream Dagster asset or external?
7. **Authentication** on FastAPI endpoints — spec is silent.

---

## 8. Recommendations (for human decision — next step: `/sc:design`)

1. **Adopt** the domain-sliced monorepo layout in §1.
2. **Adopt** MLflow tracking + registry for model exchange (§2). Drop the shared `model_store` volume.
3. **Adopt** the four-service Dagster compose layout (§5) — or explicitly document that Phase 1 uses the simplified variant and plan the migration.
4. **Adopt** `lifespan` + `APIRouter` + `Depends()` on FastAPI (§4). Decide cold-start policy up front.
5. **Adopt** the framework-free `DataWhiskDB` with per-framework adapters (§6).
6. **Use** `dagster-mlflow` resource + `MaterializeResult` metadata on the asset (§3).
7. **Resolve** the seven open questions in §7 before implementation.

---

## Sources

- [Deploying Dagster using Docker Compose — Dagster Docs](https://docs.dagster.io/deployment/oss/deployment-options/docker)
- [Dagster I/O managers guide](https://docs.dagster.io/guides/build/io-managers)
- [Dagster assets API reference](https://docs.dagster.io/api/dagster/assets)
- [What Are Software-Defined Assets? — Dagster blog](https://dagster.io/blog/software-defined-assets)
- [Dagster ML full-pipeline example (ModelStorage abstraction)](https://github.com/dagster-io/dagster/blob/master/docs/docs/examples/full-pipelines/ml/3-evaluation-deployment.md)
- [FastAPI Lifespan events](https://fastapi.tiangolo.com/advanced/events)
- [FastAPI APIRouter reference](https://fastapi.tiangolo.com/reference/apirouter)
- [FastAPI SQL databases tutorial (dependency injection)](https://fastapi.tiangolo.com/tutorial/sql-databases)
- [Full Stack FastAPI Template](https://fastapi.tiangolo.com/project-generation/)
- [Dagster + Weights & Biases (joblib serialization supported)](https://docs.wandb.ai/models/integrations/dagster)
- [Dockerizing FastAPI with Postgres — TestDriven.io](https://testdriven.io/blog/fastapi-docker-traefik/)
- [MLflow Model Registry concepts](https://mlflow.org/docs/latest/model-registry.html)
- [MLflow tracking server with Postgres backend](https://mlflow.org/docs/latest/tracking/server.html)
- [dagster-mlflow integration](https://docs.dagster.io/api/libraries/dagster-mlflow)

---

## Phase 1 Decisions (locked 2026-04-15)

| # | Question | Decision | Notes |
|---|---|---|---|
| 1 | Model promotion | **Manual** via MLflow UI | Revisit for validation-gated auto-promote once baseline metrics exist |
| 2 | Cold start | **Load-on-request**, return 503 if no `Production` model | Add in-memory caching / model-pool in a later phase |
| 3 | Postgres topology | **DataWhisk DB lives on an external server** (connection string via `.env`). **One local Postgres container** for Dagster + MLflow, two databases (`dagster`, `mlflow`) | Migrate Dagster/MLflow DBs to the external server later |
| 4 | MLflow artifact store | **Local Docker named volume**, MLflow started with `--serve-artifacts` | Swap to MinIO/S3 on server migration |
| 5 | Dagster run launcher | **In-process** (webserver/daemon execute assets directly) | Revisit if training jobs get heavy |
| 6 | Sensor data ingestion | **Out of scope.** External system writes `occupancy_logs`; DataWhisk reads only | No ingestion asset needed |
| 7 | Authentication | **None** (internal network / dev only) | Add API-key header when exposed beyond localhost |

**Next step:** Run `/sc:design "DataWhisk Occupancy Service architecture" --persona-architect --format spec` to convert these findings into an implementation blueprint, then `/sc:implement` against that design.
