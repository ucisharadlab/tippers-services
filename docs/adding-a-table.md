# Adding a New Table to the Pydantic Layer

The `shared/datawhisk_shared` package is the single source of truth for how DataWhisk reads from the external Postgres. Both the FastAPI service and the Dagster orchestrator import from it.

This guide walks through adding a new table end-to-end.

---

## The three-file pattern

For any new table you want to read, touch exactly these files:

1. `shared/datawhisk_shared/models.py` — add the Pydantic model
2. `shared/datawhisk_shared/database.py` — add the read method
3. `shared/datawhisk_shared/__init__.py` — export the model

Then add tests in `tests/shared/test_database.py`.

---

## Example: adding the `sensor` table

Suppose the external DB has:

```
Table "public.sensor"
  Column    |           Type           | Nullable
------------+--------------------------+---------
 sensor_id  | integer                  | not null
 space_id   | integer                  |
 sensor_type| text                     |
 installed  | timestamp without time zone
```

### Step 1 — Pydantic model

In `shared/datawhisk_shared/models.py`:

```python
class Sensor(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sensor_id: int
    space_id: int | None = None
    sensor_type: str | None = None
    installed: datetime | None = None

    @field_validator("installed", mode="after")
    @classmethod
    def _assume_utc(cls, v):
        return v.replace(tzinfo=timezone.utc) if v and v.tzinfo is None else v
```

**Rules:**
- Use `from_attributes=True` so `model_validate(dict_from_db_row)` works.
- Any `NOT NULL` column → required field, no default.
- Any nullable column → `| None = None`.
- `timestamp without time zone` columns → add a `field_validator` to coerce naive → UTC-aware. (The external DB stores timestamps naively; downstream code compares them with tz-aware query params.)
- Custom Postgres types (`json`, `coordinate[]`, etc.) → use permissive types: `dict | list | None`, `list[Any] | None`. Tighten later when you know the actual shape.

### Step 2 — DB method

In `shared/datawhisk_shared/database.py`:

```python
def get_sensors_for_space(self, space_id: int) -> list[Sensor]:
    query = text(
        "SELECT * FROM sensor WHERE space_id = :space_id ORDER BY sensor_id"
    )
    with self._engine.connect() as conn:
        rows = conn.execute(query, {"space_id": space_id}).mappings().all()
    return [Sensor.model_validate(dict(r)) for r in rows]
```

**Rules:**
- Always use SQLAlchemy `text()` with named parameters (`:foo`) — never f-strings (SQL injection).
- Use `.mappings().all()` to get dict-like rows; `.all()` returns tuples which are harder to bind.
- Wrap each row in `Model.model_validate(dict(row))`.
- For single-row lookups: `.first()` + `return Model(...) if row else None`.
- Don't import FastAPI or Dagster in this file. `shared/` stays framework-free.

### Step 3 — Export

In `shared/datawhisk_shared/__init__.py`:

```python
from datawhisk_shared.database import DataWhiskDB
from datawhisk_shared.models import OccupancyRow, Sensor, Space

__all__ = ["DataWhiskDB", "OccupancyRow", "Sensor", "Space"]
```

### Step 4 — Tests

In `tests/shared/test_database.py`, use the existing SQLite fixture pattern:

```python
# In the sqlite_url fixture, add table creation + seed rows:
conn.execute(text("""
    CREATE TABLE sensor (
        sensor_id INTEGER PRIMARY KEY,
        space_id INTEGER,
        sensor_type TEXT,
        installed TIMESTAMP
    )
"""))
conn.execute(text(
    "INSERT INTO sensor VALUES "
    "(1, 42, 'co2', '2025-01-01 00:00:00'),"
    "(2, 42, 'temp', '2025-02-01 00:00:00')"
))

# Then:
def test_get_sensors_for_space(sqlite_url):
    db = DataWhiskDB(sqlite_url)
    sensors = db.get_sensors_for_space(42)
    assert len(sensors) == 2
    assert sensors[0].sensor_type == "co2"
```

Run: `pytest tests/shared`.

---

## Using the model

From FastAPI:

```python
from datawhisk_shared import Sensor
from api.deps import DBDep

@router.get("/spaces/{space_id}/sensors", response_model=list[Sensor])
def list_sensors(space_id: int, db: DBDep):
    return db.get_sensors_for_space(space_id)
```

FastAPI auto-serializes a `list[Sensor]` — no manual conversion.

From Dagster:

```python
@dg.asset
def some_asset(db: DataWhiskDBResource):
    sensors = db.get_client().get_sensors_for_space(42)
    for s in sensors:
        print(s.sensor_type)  # fully typed
```

---

## Common pitfalls

| Pitfall | Fix |
|---|---|
| `TypeError: can't compare offset-naive and offset-aware datetimes` | Add `field_validator` to the timestamp field in the Pydantic model |
| `ValidationError: Input should be a valid integer` | A column you declared `int` has NULLs; change to `int \| None = None` |
| `could not determine type of "extent"` with `json` columns | Use `dict \| list \| None`, not `dict` |
| Adding a field works locally but fails in Docker | You forgot to rebuild: `docker compose up -d --build api` |
| Tests pass but runtime fails on Postgres | SQLite types are permissive; Postgres isn't. Always prefer matching types to the real schema (`NUMERIC` → `Decimal`, not `float`). |

---

## Don't put these in `shared/`

- Request/response schemas specific to an API route → `api/schemas.py`
- Dagster resources → `orchestration/resources.py`
- Anything FastAPI- or Dagster-specific

`shared/` is the intersection of concerns. If only one service needs something, it doesn't belong here.
