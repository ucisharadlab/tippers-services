# DataWhisk Architecture

This page explains the four layers DataWhisk code is split into and how requests/runs flow through them. Read it once when onboarding; after that, use `adding-a-table.md`, `adding-an-endpoint.md`, and `adding-a-dagster-asset.md` as recipes.

---

## The four layers

```
  ┌──────────────────────────────────────────────────────┐
  │  L4  Route (FastAPI)        Asset (Dagster)          │
  │      api/routes/*.py        orchestration/assets/*.py│
  └──────┬───────────────────────────────┬───────────────┘
         │                               │
         │ SessionDep                    │ DataWhiskSessionResource.session()
         ▼                               ▼
  ┌──────────────────────────────────────────────────────┐
  │  L3  Session (per request / per asset call)          │
  │      sqlalchemy.orm.Session                          │
  └──────────────────────┬───────────────────────────────┘
                         │
                         │ select(Occupancy).where(...)
                         ▼
  ┌──────────────────────────────────────────────────────┐
  │  L2  ORM (DB shape)                                  │
  │      shared/datawhisk_shared/orm.py                  │
  └──────────────────────┬───────────────────────────────┘
                         │
                         │ OccupancyRow.model_validate(orm_row)
                         ▼
  ┌──────────────────────────────────────────────────────┐
  │  L1  Pydantic DTO (API shape)                        │
  │      shared/datawhisk_shared/models.py               │
  └──────────────────────────────────────────────────────┘
```

Each layer has one job. Crossing a layer boundary is an explicit call, never an implicit one.

| Layer | Concern | File(s) |
|---|---|---|
| L1 Pydantic DTO | Shape returned to HTTP clients. UTC coercion, field defaults, validators. | `shared/datawhisk_shared/models.py` |
| L2 ORM | Shape of the real Postgres table. Columns, types, PK. | `shared/datawhisk_shared/orm.py` |
| L3 Session | Connection lifecycle (per-request on API, per-asset-call on Dagster). | `shared/datawhisk_shared/session.py`, `api/deps.py`, `orchestration/resources.py` |
| L4 Route / Asset | Business logic: query, transform, return or materialize. | `api/routes/*.py`, `orchestration/assets/*.py` |

---

## Why two `Space` classes?

There is an ORM `Space` in `datawhisk_shared.orm` and a Pydantic `Space` in `datawhisk_shared.models`. They describe the same table but exist for different reasons:

- **ORM `Space`** reflects what is actually in Postgres, including quirks like `space_shape: Text` (PostGIS WKT) and `vertices: ARRAY(Text)` (custom composite type). SQLAlchemy uses it to build SQL and hydrate rows from the driver.
- **Pydantic `Space`** is the HTTP-wire shape. It has permissive unions (`dict | list | None` for the JSON columns), a UTC-coercing validator for timestamps, and `from_attributes=True` so `Space.model_validate(orm_row)` bridges the two.

The DTO is not a subset or a copy of the ORM, they can diverge. A field can exist in the ORM but not the DTO (never exposed) or in the DTO but not the ORM (computed).

**Rule:** `shared/datawhisk_shared/__init__.py` re-exports only the Pydantic DTOs. Callers that need the ORM class import it explicitly and alias when both are in scope:

```python
from datawhisk_shared import Space                     # Pydantic
from datawhisk_shared.orm import Space as SpaceORM     # ORM
```

---

## Why `SessionDep` and `DataWhiskSessionResource` instead of one facade?

The first version of this codebase wrapped SQLAlchemy in a `DataWhiskDB` facade that exposed hand-written methods like `pull_historical_occupancy(space_id, start, end)`. That was removed. The current pattern:

- **FastAPI** uses `SessionDep` (an `Annotated[Session, Depends(get_session)]`) so every request gets its own session, opened and closed by FastAPI's generator-dependency protocol.
- **Dagster** uses `DataWhiskSessionResource.session()` (a `@contextmanager`) so every asset run opens a session scoped to its own `with` block.

Two idioms, one underlying engine pattern (both go through `datawhisk_shared.session.make_sessionmaker`). The tradeoff is:

| Facade (old) | Session pattern (current) |
|---|---|
| Central place for every query, testable in isolation | Queries live next to the logic that uses them |
| Every new query = new method = new test of the facade | Every new query = inline `select(...)`, test the route/asset |
| Hides SQLAlchemy | Leans into SQLAlchemy 2.0 |
| Breaks if the caller needs a query the facade doesn't expose | Caller builds the query they need |

The session pattern is the standard FastAPI + SQLAlchemy 2.0 idiom. It trades centralization for flexibility, which pays off once more than one or two callers start needing variations of each query.

---

## Request flow (API)

1. Client hits `GET /services/occupancy/42?start=...&end=...`.
2. FastAPI resolves `SessionDep`, which runs `get_session()` in `api/deps.py`, yielding a fresh `Session` from the shared `sessionmaker`.
3. The route (`api/routes/occupancy.py`) issues `select(Occupancy).where(...)` statements through the session.
4. Rows come back as ORM `Occupancy` instances.
5. The route converts: `OccupancyRow.model_validate(r)` per row. Pydantic's `_assume_utc` validator re-attaches `tzinfo=UTC` for every naive datetime.
6. The route assembles an `OccupancyResponse` (schema in `api/schemas.py`) and returns it.
7. FastAPI serializes the Pydantic response. The session is closed by the generator's `finally` block.

**Timezone boundary:** the route uses the helper `_to_db(dt)` (`api/routes/occupancy.py`) to strip tz before binding a datetime into a WHERE clause. Tippers stores `timestamp without time zone`; mixing tz-aware and tz-naive in a comparison gives silent wrongness on SQLite and deprecation warnings on Postgres. Strip at the DB boundary, re-attach on the way out. See `docs/adding-a-table.md` for the rule.

---

## Run flow (Dagster)

1. Dagster schedules or user triggers `occupancy_model` (`orchestration/assets/occupancy.py`).
2. The asset receives a `DataWhiskSessionResource` injection (wired in `orchestration/definitions.py` from `DATABASE_URL`).
3. The asset opens a session: `with db.session() as session:`.
4. It issues ORM queries and converts rows to Pydantic DTOs, same pattern as the API.
5. Training / MLflow logging runs inside the `with` block (or after, if the session is no longer needed).
6. The asset returns a `dg.MaterializeResult` with metadata. Dagster records it.

**Why a per-call session, not a per-run session?** Because `DataWhiskSessionResource.session()` is a context manager, you get the lifecycle benefits (auto-close on exception) without having to reason about long-lived state across the whole asset run. For batch work the overhead of creating an engine per call is negligible.

---

## What lives where

```
shared/datawhisk_shared/
  base.py       DeclarativeBase — the anchor for all ORM models
  orm.py        ORM table mappings (L2)
  models.py     Pydantic DTOs   (L1)
  session.py    make_sessionmaker factory (L3 primitive)
  __init__.py   Re-exports DTOs + make_sessionmaker. Does NOT re-export ORM.

api/
  deps.py       SessionDep (L3 for FastAPI)
  routes/       One file per domain (occupancy, models, ...)
  schemas.py    Request/response shapes specific to HTTP endpoints
  main.py       App assembly, health/ready probes
  mlflow_utils.py  Model registry glue (ModelResolver, run_for_space, ...)

orchestration/
  resources.py  DataWhiskSessionResource (L3 for Dagster)
  definitions.py Assembly: assets + resources = Definitions
  assets/       One file per domain (occupancy, thermal, ...)
```

The `shared/` package is **framework-free**. It never imports from `fastapi`, `dagster`, `api.*`, or `orchestration.*`. This is what lets both services depend on it without creating a circular dependency.

---

## Cross-references

- **Add a new table**: [`adding-a-table.md`](adding-a-table.md)
- **Add a new API endpoint**: [`adding-an-endpoint.md`](adding-an-endpoint.md)
- **Add a new Dagster asset**: [`adding-a-dagster-asset.md`](adding-a-dagster-asset.md)
- **API reference**: [`api-reference.md`](api-reference.md)
