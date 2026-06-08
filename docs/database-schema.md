# Database Schema

This document covers every table DataWhisk reads from or writes to, the database systems involved, how connections are managed, and the conventions every caller must follow. Read [`architecture.md`](architecture.md) first for the layered model (ORM → DTO → Route/Asset) that this document builds on.

---

## Database systems

DataWhisk connects to two distinct PostgreSQL 16 instances.

| Instance | Purpose | Access | Host |
|---|---|---|---|
| **Tippers** (`datawhisk_capstone`) | Live sensor data: occupancy, spaces, sensors, VAV zone mappings | Read-only | `sensoria-2.ics.uci.edu:5432` |
| **Local Docker** | Dagster run history, MLflow experiment/model metadata | Read-write (managed by the frameworks) | `localhost:5432` (via `docker-compose.yml`) |

The `DATABASE_URL` environment variable controls which Tippers instance each service connects to. The local Docker instance runs two databases:

```sql
CREATE DATABASE dagster;   -- Dagster event log and run storage
CREATE DATABASE mlflow;    -- MLflow tracking server metadata
```

These are bootstrapped by [`infra/postgres/init.sql`](../infra/postgres/init.sql) and are entirely managed by Dagster and MLflow — DataWhisk code never queries them directly.

---

## Connection management

All application connections go through a single factory in [`shared/datawhisk_shared/session.py`](../shared/datawhisk_shared/session.py):

```python
def make_sessionmaker(database_url: str) -> sessionmaker[Session]:
    engine = create_engine(database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
```

`pool_pre_ping=True` ensures stale connections are recycled automatically. `expire_on_commit=False` prevents attribute-access errors after a `session.commit()`, which matters for the `model_space_mapping` upsert pattern.

The session lifetime differs between services:

| Service | Session scope | Mechanism |
|---|---|---|
| FastAPI | One per HTTP request | `SessionDep` in `api/deps.py` (generator dependency) |
| Dagster | One per asset `with` block | `DataWhiskSessionResource.session()` context manager |

---

## ORM source of truth

All table definitions live in [`shared/datawhisk_shared/orm.py`](../shared/datawhisk_shared/orm.py). SQLAlchemy 2.0 `Mapped` annotations are used throughout. The ORM reflects existing DDL — it does **not** generate or run migrations.

---

## Tables

### `space`

Hierarchical catalog of building spaces (rooms, floors, buildings). Sourced from Tippers; treated as read-only.

| Column | Postgres type | Nullable | Notes |
|---|---|---|---|
| `space_id` | `integer` | NOT NULL | Primary key |
| `space_name` | `text` | NOT NULL | Human-readable label |
| `parent_space_id` | `integer` | YES | Self-referential: parent in the space tree |
| `coordinate_system_name` | `text` | YES | Name of the coordinate system used |
| `space_shape` | `text` | YES | PostGIS WKT geometry string |
| `extent` | `json` | YES | Bounding box or extent data |
| `space_type_id` | `integer` | YES | Reference to space-type lookup |
| `gps_extent` | `json` | YES | GPS bounding box |
| `radius` | `numeric` | YES | Spatial radius, if applicable |
| `vertices` | `coordinate[]` | YES | Polygon vertices (custom composite type — mapped as `ARRAY(Text)`) |
| `gps_vertices` | `coordinate[]` | YES | GPS polygon vertices (same caveat) |

**Hierarchy:** `parent_space_id` is a self-join back to `space_id`. A NULL parent means the space is a root node (e.g., the whole building).

**Composite-type caveat:** `vertices` and `gps_vertices` use a custom Postgres composite type (`coordinate[]`). The ORM maps them as `ARRAY(Text)` — a pragmatic placeholder. Direct reads of these columns may return garbled data; use a `TypeDecorator` or raw SQL if precise vertex parsing is needed.

**API-used queries:**

```python
# Fetch space names for the frontend tree
select(Space.space_id, Space.space_name)

# Fetch immediate children of a space
select(Space.space_id).where(Space.parent_space_id == parent_id)
```

**Routes:** [`api/routes/spaces.py`](../api/routes/spaces.py)

---

### `occupancy`

Time-series occupancy counts per space. Sourced from Tippers; treated as read-only. The Postgres table has no declared primary key — the ORM uses a virtual composite key so SQLAlchemy can maintain its identity map.

| Column | Postgres type | Nullable | Notes |
|---|---|---|---|
| `spaceid` | `integer` | YES | Space identifier (joins to `space.space_id`) |
| `starttime` | `timestamp without time zone` | YES | Interval start — naive UTC |
| `endtime` | `timestamp without time zone` | YES | Interval end — naive UTC |
| `occupancy` | `integer` | YES | Count of people detected during the interval |

**Virtual PK:** Because the table has no real primary key, the ORM mapper declares one:

```python
__mapper_args__ = {
    "primary_key": [spaceid, starttime, endtime],
}
```

This is a mapper-only declaration and emits no DDL. It is safe against the Tippers schema.

**Datetime boundary rule:** `starttime` and `endtime` are stored as naive timestamps (Postgres `timestamp without time zone`). The assumed timezone is UTC. When binding a tz-aware datetime into a `WHERE` clause, strip the timezone first:

```python
def _to_db(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt

select(Occupancy).where(
    Occupancy.starttime >= _to_db(start),
    Occupancy.endtime   <= _to_db(end),
)
```

On the read side, the Pydantic DTO's `_assume_utc` validator re-attaches `UTC` before the row is returned to HTTP clients.

**API-used queries:**

```python
# Check whether a space has any data
select(func.count()).where(Occupancy.spaceid == space_id)

# All spaces that have at least one row
select(func.distinct(Occupancy.spaceid))

# All rows for a space (used for model training)
select(Occupancy).where(Occupancy.spaceid == space_id)

# Latest timestamp in the dataset
select(func.max(Occupancy.endtime))
```

**Routes:** [`api/routes/occupancy.py`](../api/routes/occupancy.py)  
**Assets:** [`orchestration/assets/occupancy.py`](../orchestration/assets/occupancy.py)

---

### `sensor`

Catalog of physical sensors installed in spaces. Sourced from Tippers; treated as read-only. Defined in the ORM but not actively queried by current API routes or assets.

| Column | Postgres type | Nullable | Notes |
|---|---|---|---|
| `sensor_id` | `integer` | NOT NULL | Primary key |
| `sensor_name` | `text` | NOT NULL | Human-readable label |
| `sensor_type_id` | `integer` | YES | Reference to sensor-type lookup |
| `property_values` | `json` | YES | Arbitrary key-value properties |
| `space_id` | `integer` | YES | The space this sensor is installed in |

---

### `zone_vav_mapping`

Maps WiFi access points to VAV (Variable Air Volume) HVAC zones and building spaces. Composite primary key on `(wifi_ap, space_id)`. Sourced from Tippers; treated as read-only.

| Column | Postgres type | Nullable | Notes |
|---|---|---|---|
| `wifi_ap` | `text` | NOT NULL | WiFi AP identifier (part of composite PK) |
| `space_id` | `integer` | NOT NULL | Building space (part of composite PK) |
| `vav_name` | `text` | NOT NULL | VAV zone name, e.g. `"VAV-101"` |

**Purpose:** Occupancy data is keyed by `space_id`; thermal/HVAC data is keyed by VAV zone name. This table is the join that connects the two domains. It also links WiFi APs (which Tippers uses to derive occupancy) back to zones.

**Key queries used by the thermal service:**

```python
# Build the zone → space_id cache
select(ZoneVavMapping.vav_name, ZoneVavMapping.space_id)

# Build the zone → wifi_ap cache
select(ZoneVavMapping.vav_name, ZoneVavMapping.wifi_ap)

# All distinct VAV zones (used to populate the UI dropdown)
SELECT DISTINCT vav_name FROM zone_vav_mapping ORDER BY vav_name
```

**Routes:** [`api/routes/thermal.py`](../api/routes/thermal.py)

---

### `model_space_mapping`

The only table that DataWhisk creates and owns. Tracks which MLflow model version (occupancy and thermal) is currently active for each space, and when it was last trained.

| Column | Postgres type | Nullable | Notes |
|---|---|---|---|
| `space_id` | `integer` | NOT NULL | Primary key; joins to `space.space_id` |
| `occupancy_model_uri` | `text` | YES | MLflow URI, format: `models:/{name}@{alias}` |
| `thermal_model_uri` | `text` | YES | MLflow URI, format: `models:/{name}@{alias}` |
| `last_trained` | `timestamp with time zone` | YES | UTC timestamp of the last training run |
| `last_run_id` | `text` | YES | Dagster run ID that produced the current models |

**URI format:** Both model URI columns use the MLflow registered-model alias syntax: `models:/datawhisk-occupancy-42@production`. The alias (e.g. `@production`) is assigned manually in the MLflow UI after reviewing a new model. See [MLflow alias management preference](../memory/feedback_mlflow_alias.md).

**Upsert pattern** (used in [`orchestration/assets/occupancy.py`](../orchestration/assets/occupancy.py)):

```python
def upsert_model_mapping(session, space_id, model_uri, run_id):
    row = session.get(ModelSpaceMapping, space_id)
    if row is None:
        row = ModelSpaceMapping(space_id=space_id)
        session.add(row)
    row.occupancy_model_uri = model_uri
    row.last_run_id = run_id
    row.last_trained = datetime.now(tz=timezone.utc)
    session.commit()
```

**Written by:** [`orchestration/assets/occupancy.py`](../orchestration/assets/occupancy.py) after a successful occupancy model training run.  
**Read by:** [`api/routes/mapping.py`](../api/routes/mapping.py) (`GET /services/mapping/{space_id}`), and occupancy/thermal prediction routes to resolve which model to load from MLflow.

---

## Relationships

```
space
  ├── parent_space_id ──► space.space_id   (self-referential hierarchy)
  │
  ├── occupancy.spaceid ──► space.space_id (implicit, no FK declared in Tippers)
  │
  ├── sensor.space_id ──► space.space_id   (implicit)
  │
  ├── zone_vav_mapping.space_id ──► space.space_id  (composite PK member)
  │
  └── model_space_mapping.space_id ──► space.space_id

zone_vav_mapping
  ├── (wifi_ap, space_id) — composite primary key
  └── vav_name — links to HVAC system; no FK (external system)

model_space_mapping
  ├── occupancy_model_uri ──► MLflow registered model
  └── thermal_model_uri   ──► MLflow registered model
```

No explicit foreign-key constraints are declared in the Tippers schema. The ORM does not declare `ForeignKey(...)` columns either — relationships are enforced at the application layer by consistent use of `space_id` as the shared key across all tables.

---

## Pydantic DTOs

Every table that is returned over HTTP has a corresponding Pydantic DTO in [`shared/datawhisk_shared/models.py`](../shared/datawhisk_shared/models.py). The DTO is not a copy of the ORM — it is the HTTP-wire shape and can diverge:

- A column in the ORM may be absent from the DTO (never exposed to clients).
- A field in the DTO may be absent from the ORM (computed, defaulted, or synthesized).
- `_assume_utc` validators on datetime fields re-attach `UTC` to naive timestamps before serialization.

The DTO is bridged from the ORM row via Pydantic's `from_attributes=True` config:

```python
OccupancyRow.model_validate(orm_row)
```

Import convention to avoid name collisions:

```python
from datawhisk_shared import Space               # Pydantic DTO
from datawhisk_shared.orm import Space as SpaceORM  # ORM class
```

---

## Adding a new table

See [`adding-a-table.md`](adding-a-table.md) for the step-by-step recipe (ORM model → Pydantic DTO → export → tests).

---

## Cross-references

- **Architecture overview**: [`architecture.md`](architecture.md)
- **Adding a table**: [`adding-a-table.md`](adding-a-table.md)
- **Adding an API endpoint**: [`adding-an-endpoint.md`](adding-an-endpoint.md)
- **Adding a Dagster asset**: [`adding-a-dagster-asset.md`](adding-a-dagster-asset.md)
- **API reference**: [`api-reference.md`](api-reference.md)
