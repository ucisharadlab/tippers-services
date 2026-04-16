# Adding a New API Endpoint

Before reading: see [`architecture.md`](architecture.md) for the four-layer model and [`adding-a-table.md`](adding-a-table.md) if the endpoint reads from a table that does not yet have an ORM model.

This guide shows the full pattern for a new FastAPI endpoint: route file, response schema, DB access, wiring, and tests.

---

## The four-file pattern

For any new endpoint, touch these:

1. `api/routes/<domain>.py` — the route handler. One file per domain.
2. `api/schemas.py` — Pydantic request/response shapes specific to HTTP.
3. `api/main.py` — register the router with the app.
4. `tests/api/test_<domain>_route.py` — in-memory SQLite test with `dependency_overrides`.

The shared `datawhisk_shared` package (DTOs, ORM, `make_sessionmaker`) stays untouched unless you are adding a new table.

---

## Example: `GET /services/sensors/{space_id}/latest`

Returns the most recent reading per sensor for a space. Assume `Sensor` ORM + Pydantic DTO already exist per [`adding-a-table.md`](adding-a-table.md).

### Step 1 — Define the route

Create `api/routes/sensors.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from api.deps import SessionDep
from api.schemas import LatestSensorsResponse
from datawhisk_shared import Sensor
from datawhisk_shared.orm import Sensor as SensorORM

router = APIRouter(prefix="/services/sensors", tags=["sensors"])


@router.get("/{space_id}/latest", response_model=LatestSensorsResponse)
def latest_readings(space_id: int, session: SessionDep) -> LatestSensorsResponse:
    rows = session.scalars(
        select(SensorORM)
        .where(SensorORM.space_id == space_id)
        .order_by(SensorORM.sensor_id)
    ).all()
    if not rows:
        raise HTTPException(404, f"no sensors for space_id={space_id}")
    return LatestSensorsResponse(
        space_id=space_id,
        sensors=[Sensor.model_validate(r) for r in rows],
    )
```

**Rules:**
- One `APIRouter` per file. Pick a `prefix` and put the domain name in `tags` (it groups the endpoint in `/docs`).
- Take `session: SessionDep` as a parameter. Never import `make_sessionmaker` directly from a route, that defeats dependency-override-based testing.
- Build queries with `select(...)` from `sqlalchemy`. Use the ORM class (aliased as `SensorORM` to avoid collision with the Pydantic `Sensor`).
- Convert ORM rows to Pydantic DTOs at the return statement: `[Sensor.model_validate(r) for r in rows]`. Do not return raw ORM instances.
- For binary precondition failures use `raise HTTPException(status_code, detail)`. Do not return dicts with error fields; let FastAPI's error-body format do its job.
- If you bind a tz-aware datetime into a `where(...)`, strip tz first with a helper like `_to_db(dt)` in `api/routes/occupancy.py`. See [`adding-a-table.md`](adding-a-table.md) for the rule.

### Step 2 — Define the response schema

In `api/schemas.py`:

```python
from datawhisk_shared import Sensor

class LatestSensorsResponse(BaseModel):
    space_id: int
    sensors: list[Sensor]
```

**Rules:**
- Response models with nested DTOs work out of the box as long as the DTO has `from_attributes=True` (every DTO in `datawhisk_shared.models` does).
- For responses that wrap the same primary type in different contexts, define a separate wrapper class, do not overload one class with optional fields.
- If a field name collides with a Pydantic-reserved namespace (like `model_*`), add `model_config = ConfigDict(protected_namespaces=())`, see `OccupancyResponse` for the pattern.
- Keep request shapes (if any) in this file too. Read the file before adding, it is the one place where HTTP-layer types live.

### Step 3 — Register the router

In `api/main.py`:

```python
from api.routes import models, occupancy, sensors  # add sensors

app.include_router(sensors.router)
```

That is it. The router's `prefix` and `tags` are already set in the route file, so no additional config here.

### Step 4 — Tests

Create `tests/api/test_sensors_route.py`:

```python
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.deps import get_session
from api.main import app
from datawhisk_shared.base import Base
from datawhisk_shared.orm import Sensor


@pytest.fixture
def sm(tmp_path):
    url = f"sqlite:///{tmp_path/'test.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine, tables=[Sensor.__table__])
    with Session(engine) as s:
        s.add_all([
            Sensor(sensor_id=1, space_id=42, sensor_type="co2", installed=datetime(2026, 1, 1)),
            Sensor(sensor_id=2, space_id=42, sensor_type="temp", installed=datetime(2026, 2, 1)),
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


def test_returns_sensors_for_space(client):
    r = client.get("/services/sensors/42/latest")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["space_id"] == 42
    assert len(body["sensors"]) == 2


def test_404_on_empty_space(client):
    r = client.get("/services/sensors/999/latest")
    assert r.status_code == 404
```

**Rules:**
- Use the in-memory SQLite pattern from `tests/api/test_occupancy_route.py`. One engine per test via `tmp_path`, or `sqlite:///:memory:` if the test does not need persistence across calls.
- `Base.metadata.create_all(engine, tables=[Sensor.__table__])` creates only the tables you want. Important if another ORM model uses a Postgres-only type (e.g., `Space.vertices` is `ARRAY(Text)` which SQLite cannot create).
- Override `get_session` (not `SessionDep`) in `dependency_overrides`. The `Annotated` wrapper is a convention, the actual key is the generator function.
- Clear `app.dependency_overrides` in the fixture teardown or tests leak into each other.
- If the route depends on MLflow (like the occupancy route's `_resolver`), patch that module-level attribute with `unittest.mock.patch` as seen in `test_occupancy_route.py`.

---

## Request-body endpoints

For a POST/PUT with a JSON body, define the input schema in `api/schemas.py`:

```python
class CreateSensorRequest(BaseModel):
    space_id: int
    sensor_type: str
    installed: datetime | None = None
```

Then in the route:

```python
@router.post("", response_model=Sensor, status_code=201)
def create_sensor(body: CreateSensorRequest, session: SessionDep) -> Sensor:
    row = SensorORM(
        space_id=body.space_id,
        sensor_type=body.sensor_type,
        installed=body.installed,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return Sensor.model_validate(row)
```

**Rules:**
- Write endpoints need `session.commit()`. Read endpoints do not.
- After `commit()`, call `session.refresh(row)` to reload server-generated fields (autoincrement IDs, `DEFAULT` values).
- Use explicit `status_code=201` for resource creation. The default 200 is wrong for a POST that created something.
- Validate request bodies with Pydantic, not manually. FastAPI will return a 422 with field-level details automatically.

---

## Uploads (`multipart/form-data`)

See `api/routes/models.py::upload_model` for the reference pattern:

- Take `file: UploadFile = File(...)` and form fields with `Form(...)`.
- Write the upload to a `tempfile.NamedTemporaryFile(delete=False)` first, then process, then delete in a `finally` block.
- Catch domain-specific parse errors and re-raise as `HTTPException(400, ...)`, do not let `joblib`/parser tracebacks leak to the client.

---

## Health and readiness

These already exist in `api/main.py`:

- `GET /health` — always 200, no dependencies. Use for Docker/K8s liveness.
- `GET /ready` — 200 if the DB is reachable via the shared `sessionmaker`, 503 otherwise. Use for readiness.

Do not add new top-level health endpoints. If you need a domain-specific probe, put it under `/services/<domain>/health`.

---

## Common pitfalls

| Pitfall | Fix |
|---|---|
| `Depends(Depends(get_session))` in the signature | You wrote `session: Depends(get_session)` instead of `session: SessionDep`. Use the `Annotated` alias. |
| Route works in dev, 500 in tests with "No module named ..." | You forgot to import the route module in `api/main.py`. Import, then `include_router`. |
| Response has weird keys like `_sa_instance_state` | You returned an ORM instance directly instead of converting via `Pydantic.model_validate(r)`. |
| Dependency override in one test bleeds into the next | You forgot `app.dependency_overrides.clear()` in the fixture teardown. |
| `OperationalError: no such table` in tests | `Base.metadata.create_all` did not include your ORM's table. Add `tables=[YourORM.__table__]`. |
| `TypeError: can't compare offset-naive and offset-aware datetimes` | Tz-aware datetime bound into a WHERE against a `timestamp without time zone` column. Strip tz with `_to_db(dt)` first. |
| 422 on a path param that looks valid (trailing space or tab) | Real case, FastAPI strictly validates. Not a bug, strip the param client-side or relax the annotation. |

---

## Cross-references

- [`architecture.md`](architecture.md) — the four-layer model
- [`adding-a-table.md`](adding-a-table.md) — add the ORM/DTO if the endpoint reads a new table
- [`api-reference.md`](api-reference.md) — document the endpoint publicly after shipping it
- `api/routes/occupancy.py` — reference implementation for a read-heavy endpoint
- `api/routes/models.py` — reference implementation for a file-upload endpoint
