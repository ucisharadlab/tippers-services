# Adding a New Table

The `shared/datawhisk_shared` package is the single source of truth for how DataWhisk reads from the external Postgres (Tippers). Both the FastAPI service and the Dagster orchestrator import from it.

Access happens via SQLAlchemy ORM (for queries) and Pydantic (for the API-response shape). Callers open a `Session` via the framework-appropriate dependency and issue `select(...)` statements directly.

---

## The three-file pattern

For any new table you want to read, touch these files:

1. `shared/datawhisk_shared/orm.py` — add the SQLAlchemy ORM model (always).
2. `shared/datawhisk_shared/models.py` — add the Pydantic DTO (only if an API endpoint returns this shape).
3. `shared/datawhisk_shared/__init__.py` — export the Pydantic DTO.

The ORM class is **not** re-exported from `__init__.py`. Callers import it explicitly:

```python
from datawhisk_shared import Sensor             # Pydantic DTO
from datawhisk_shared.orm import Sensor as SensorORM  # ORM row
```

This avoids the name collision that happens when the same table has both a DTO and an ORM class. Alias the ORM import (`as SensorORM`) in any module that needs both.

Tests for new tables live at the **consumer** layer, not in `shared/`. API-exposed tables get tests in `tests/api/` with an in-memory SQLite fixture (see `tests/api/test_occupancy_route.py`). Orchestration-only tables get tests in `tests/orchestration/`.

---

## Example: adding the `sensor` table

Suppose the external DB has:

```
Table "public.sensor"
  Column    |            Type             | Nullable | Default
------------+-----------------------------+----------+-----------------------------
 sensor_id  | integer                     | not null | nextval('sensor_id_seq'...)
 space_id   | integer                     |          |
 sensor_type| text                        |          |
 installed  | timestamp without time zone |          |
```

### Step 1 — ORM model

In `shared/datawhisk_shared/orm.py`:

```python
class Sensor(Base):
    __tablename__ = "sensor"

    sensor_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    space_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sensor_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    installed: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
```

**Rules:**
- Reflect the real DDL exactly: if the column is nullable in Postgres, set `nullable=True`. Do not tighten.
- Real PK column → `primary_key=True`. **Table has no PK at all?** Use `__mapper_args__ = {"primary_key": [col1, col2]}` to give the mapper a virtual identity. See `Occupancy` in `orm.py` for the pattern. This does not emit DDL, so it is safe against a legacy schema.
- `timestamp without time zone` → `DateTime(timezone=False)`. Do not use `TIMESTAMP(timezone=True)` unless the column is actually `timestamptz`.
- Custom Postgres types: `json` → `JSON`, `coordinate[]` and other composite arrays → `ARRAY(Text)` with a comment noting reads may need a `TypeDecorator` (see `Space.vertices`).
- `shared/` stays framework-free. Never import FastAPI, Dagster, or `api.*` from inside `orm.py`, `models.py`, or `session.py`.

### Step 2 — Pydantic DTO

Only needed if an API endpoint returns this table. In `shared/datawhisk_shared/models.py`:

```python
class Sensor(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sensor_id: int
    space_id: int | None = None
    sensor_type: str | None = None
    installed: datetime | None = None

    @field_validator("installed", mode="after")
    @classmethod
    def _assume_utc(cls, v: datetime | None) -> datetime | None:
        return v.replace(tzinfo=timezone.utc) if v and v.tzinfo is None else v
```

**Rules:**
- `from_attributes=True` is required so `Sensor.model_validate(orm_row)` works.
- `NOT NULL` column → required field. Nullable → `| None = None`.
- Any `timestamp without time zone` field needs a `_assume_utc` validator. Tippers stores naive timestamps, but HTTP consumers expect tz-aware UTC. The validator bridges the two.

### Step 3 — Export

In `shared/datawhisk_shared/__init__.py`:

```python
from datawhisk_shared.models import OccupancyRow, Sensor, Space
from datawhisk_shared.session import make_sessionmaker

__all__ = ["OccupancyRow", "Sensor", "Space", "make_sessionmaker"]
```

Only the Pydantic DTOs get exported from the package root. The ORM classes are accessed via `datawhisk_shared.orm` to keep the namespaces separate.

### Step 4 — Tests

No shared test file. Write tests where the table is consumed:

- **API:** copy the fixture pattern from `tests/api/test_occupancy_route.py` (in-memory SQLite + `Base.metadata.create_all(engine, tables=[SensorORM.__table__])` + seed rows + `app.dependency_overrides[get_session]`).
- **Orchestration:** subclass `DataWhiskSessionResource` and yield a SQLite-backed `Session` from `session()` (see `tests/orchestration/test_occupancy_asset.py`).

Run: `pytest tests/api` or `pytest tests/orchestration`.

---

## Using the model

### From FastAPI

```python
from sqlalchemy import select

from api.deps import SessionDep
from datawhisk_shared import Sensor
from datawhisk_shared.orm import Sensor as SensorORM

@router.get("/spaces/{space_id}/sensors", response_model=list[Sensor])
def list_sensors(space_id: int, session: SessionDep) -> list[Sensor]:
    rows = session.scalars(
        select(SensorORM)
        .where(SensorORM.space_id == space_id)
        .order_by(SensorORM.sensor_id)
    ).all()
    return [Sensor.model_validate(r) for r in rows]
```

`SessionDep` is defined in `api/deps.py` and wraps one request in one `Session` via a generator. The session is closed automatically when the request finishes.

### From Dagster

```python
from sqlalchemy import select

from datawhisk_shared.orm import Sensor as SensorORM
from orchestration.resources import DataWhiskSessionResource

@dg.asset
def sensor_inventory(context, db: DataWhiskSessionResource) -> dg.MaterializeResult:
    with db.session() as session:
        sensors = session.scalars(
            select(SensorORM).where(SensorORM.space_id == 42)
        ).all()
        ...
```

`DataWhiskSessionResource.session()` is a `@contextmanager`. The session lives for the duration of the `with` block, one engine + one session per `.session()` call. That is fine for the batch-job cadence Dagster runs at.

### The DB-boundary datetime rule

Tippers stores timestamps **naive** (`timestamp without time zone`), but HTTP clients and Python code routinely deal in **tz-aware** datetimes. Mixing the two in a `WHERE` clause causes silent wrongness on SQLite (string-compare of mismatched ISO formats) and deprecation warnings / errors on Postgres.

Convert at the DB boundary. Pattern in `api/routes/occupancy.py`:

```python
def _to_db(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt
```

Use `_to_db(my_dt)` when binding a datetime into a `select().where(...)`. The Pydantic `_assume_utc` validator adds UTC back on the read side.

---

## Common pitfalls

| Pitfall | Fix |
|---|---|
| `TypeError: can't compare offset-naive and offset-aware datetimes` | Strip tz before the ORM query (`_to_db(dt)`) and add `_assume_utc` to the Pydantic field. |
| `ValidationError: Input should be a valid integer` | A column declared `int` has NULLs. Change the Pydantic field to `int \| None = None` and the ORM column to `nullable=True`. |
| `InvalidRequestError: Mapper ... could not assemble any primary key` | The Postgres table has no PK. Add `__mapper_args__ = {"primary_key": [col1, col2]}` using columns that are unique in practice. |
| `DataError` or garbled rows when reading a `coordinate[]` column | `ARRAY(Text)` is a pragmatic placeholder, not a correct type. For real reads, write a `TypeDecorator` or drop to raw SQL for that one query. |
| Name clash `Space` vs `Space` | Alias the ORM import: `from datawhisk_shared.orm import Space as SpaceORM`. |
| Tests pass on SQLite but runtime fails on Postgres | SQLite tolerates type mismatches Postgres does not. Match ORM types to the real Postgres types (`NUMERIC` → `Numeric`, not `Float`; `timestamptz` → `DateTime(timezone=True)`, not `timezone=False`). |
| Adding a field works locally but fails in Docker | Rebuild the image: `docker compose up -d --build api`. |

---

## Don't put these in `shared/`

- Request/response schemas specific to an API route → `api/schemas.py`
- Dagster resources or assets → `orchestration/`
- Anything FastAPI- or Dagster-specific

`shared/` is the intersection of concerns. If only one service needs it, it does not belong here.
