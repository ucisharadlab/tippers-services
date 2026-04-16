# Adding a New Dagster Asset

Before reading: see [`architecture.md`](architecture.md) for the four-layer model and [`adding-a-table.md`](adding-a-table.md) if the asset reads from a table that does not yet have an ORM model.

This guide is the companion to [`adding-an-endpoint.md`](adding-an-endpoint.md), but for the orchestration side. It targets the modeling workflow: pull data from Tippers, train a model, log to MLflow, return a materialize result.

---

## The three-file pattern

For any new asset, touch these:

1. `orchestration/assets/<domain>.py` — the asset function.
2. `orchestration/assets/__init__.py` — append the asset to `all_assets`.
3. `tests/orchestration/test_<domain>_asset.py` — stub resource + `materialize(...)`.

`orchestration/definitions.py` already wires `DataWhiskSessionResource` as the `"db"` resource from the `DATABASE_URL` env var. You do not need to modify it unless you are adding a new kind of resource (new MLflow server, new external service, etc.).

---

## The session context-manager pattern

Every asset that reads from Tippers does this:

```python
with db.session() as session:
    rows = session.scalars(select(SomeORM).where(...)).all()
    # transform rows, leave the with block before long-running training
```

Close the session **before** you start long work (training, MLflow logging). The DB connection should not sit idle during a multi-minute training run. Pattern:

```python
with db.session() as session:
    rows = session.scalars(...).all()
    training_data = [SomeDTO.model_validate(r) for r in rows]
# session is now closed
model = train(training_data)   # this could take hours
mlflow.log_model(model, ...)
```

If you need multiple queries, either batch them into one `with` block (if fast) or open a fresh session per query. Do not hold a session open across training.

---

## Example: `thermal_model` asset

Mirror `orchestration/assets/occupancy.py`. Suppose you want to train a thermal model for a given space and log it to MLflow.

### Step 1 — Write the asset

Create `orchestration/assets/thermal.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import dagster as dg
from sqlalchemy import select

from api.mlflow_utils import log_and_register_sklearn
from datawhisk_shared import OccupancyRow
from datawhisk_shared.orm import Occupancy
from orchestration.resources import DataWhiskSessionResource


@dg.asset(
    description="Thermal model for a single space. Pulls 30 days of occupancy, trains, logs to MLflow.",
    group_name="thermal",
)
def thermal_model(context, db: DataWhiskSessionResource) -> dg.MaterializeResult:
    space_id = 1  # TODO: parameterize via config or partitions
    end = datetime.now(tz=timezone.utc)
    start = end - timedelta(days=30)

    start_naive = start.astimezone(timezone.utc).replace(tzinfo=None)
    end_naive = end.astimezone(timezone.utc).replace(tzinfo=None)

    with db.session() as session:
        orm_rows = session.scalars(
            select(Occupancy)
            .where(Occupancy.spaceid == space_id)
            .where(Occupancy.starttime >= start_naive)
            .where(Occupancy.starttime < end_naive)
            .order_by(Occupancy.starttime)
        ).all()
        training_rows = [OccupancyRow.model_validate(r) for r in orm_rows]

    context.log.info(f"pulled {len(training_rows)} rows for space_id={space_id}")

    # === training goes here ===
    # from sklearn.ensemble import GradientBoostingRegressor
    # model = GradientBoostingRegressor().fit(X, y)

    # === MLflow logging (when training is real) ===
    # result = log_and_register_sklearn(
    #     model=model,
    #     space_id=space_id,
    #     model_type="thermal",
    #     extra_tags={"training_rows": str(len(training_rows))},
    # )

    return dg.MaterializeResult(
        metadata={
            "rows": len(training_rows),
            "space_id": space_id,
            "training_status": "placeholder — wire sklearn + log_and_register_sklearn",
        }
    )
```

**Rules:**
- One `@dg.asset`-decorated function per asset. `description` and `group_name` are required if you want Dagster's UI to group assets sensibly.
- `context` is always the first positional param. Use `context.log.info/warning/error` for logs that should appear in the Dagster run view.
- Injected resources are keyword-typed: `db: DataWhiskSessionResource`. The key name (`db`) must match the key registered in `definitions.py`.
- Strip tz from datetimes before binding into the query. Tippers uses `timestamp without time zone`; see [`adding-a-table.md`](adding-a-table.md) for the rule.
- Convert ORM rows to Pydantic DTOs before leaving the `with` block. The DTOs have UTC-aware datetimes and predictable types, they are what the training code should consume.
- Close the session **before** training. Connections are pooled, do not hold one idle.

### Step 2 — Register the asset

In `orchestration/assets/__init__.py`:

```python
from orchestration.assets.occupancy import occupancy_model
from orchestration.assets.thermal import thermal_model

all_assets = [occupancy_model, thermal_model]

__all__ = ["all_assets", "occupancy_model", "thermal_model"]
```

That is all the wiring needed. `definitions.py` reads `all_assets` from this module and hands it to Dagster.

### Step 3 — Test

Create `tests/orchestration/test_thermal_asset.py`:

```python
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

from dagster import materialize
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from datawhisk_shared.base import Base
from datawhisk_shared.orm import Occupancy
from orchestration.assets.thermal import thermal_model
from orchestration.resources import DataWhiskSessionResource


class _StubResource(DataWhiskSessionResource):
    database_url: str = "stub://unused"

    @contextmanager
    def session(self) -> Iterator[Session]:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[Occupancy.__table__])
        sm = sessionmaker(bind=engine)
        with sm() as s:
            now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
            s.add(Occupancy(
                spaceid=1,
                starttime=now - timedelta(hours=1),
                endtime=now,
                occupancy=10,
            ))
            s.commit()
            yield s


def test_thermal_asset_materializes():
    result = materialize([thermal_model], resources={"db": _StubResource()})
    assert result.success
```

**Rules:**
- Subclass the real `DataWhiskSessionResource` and override `session()` to yield a SQLite-backed session. Do **not** write a bare mock: Dagster's `ConfigurableResource` is Pydantic-based, and a stub that does not inherit will fail construction validation.
- Override `database_url` with a dummy value (`"stub://unused"`). The real one is never used because your `session()` override does not call `make_sessionmaker`.
- `Base.metadata.create_all(engine, tables=[...])` limits table creation to the specific ORM you need. Important because `Space.vertices` (`ARRAY(Text)`) cannot be created on SQLite and will throw if you try to create `Space`.
- Use `materialize([asset], resources={"db": _StubResource()})` for a minimal end-to-end run. The `"db"` key must match what `definitions.py` registers; your asset signature (`db: DataWhiskSessionResource`) pulls from the same key.
- Assert `result.success`. For finer-grained assertions, inspect `result.asset_materializations_for_node("thermal_model")` to check metadata.

---

## Using MLflow from an asset

`api/mlflow_utils.py` provides two helpers that are safe to import from `orchestration/` (they do not pull in FastAPI):

- `log_and_register_sklearn(model, space_id, model_type, extra_tags)` — one-shot: start a tagged run, log the sklearn model, register a new version under `{model_type}_space_{space_id}`.
- `run_for_space(space_id, extra_tags)` — context manager for a raw MLflow run tagged with `space_id`. Use when `log_and_register_sklearn` does not fit (e.g., custom flavors, multiple log calls).

Pattern:

```python
from api.mlflow_utils import log_and_register_sklearn

result = log_and_register_sklearn(
    model=trained_model,
    space_id=space_id,
    model_type="thermal",
    extra_tags={"training_rows": str(len(rows))},
)
context.log.info(f"logged {result['registered_model_name']} v{result['version']}")
```

**Promotion is manual.** The helpers register a new version but never assign the `@production` alias. A human assigns it in the MLflow UI once they have reviewed metrics. This is intentional; see `claudedocs/design_datawhisk_occupancy_phase1_2026-04-15.md` for the decision record.

Tag runs with anything downstream queries will filter on. At minimum: `space_id`. Consider also: `training_rows`, `model_flavor`, `data_window_start`, `data_window_end`.

---

## Partitions, schedules, and sensors

Phase 1 DataWhisk runs assets on demand (materialize-all or materialize-one from the UI). If your asset needs to run on a schedule or per-partition:

- **Schedule:** add a `@dg.schedule` in a new file under `orchestration/schedules/` (create the directory) and include it in `definitions.py`.
- **Partitions:** use `dg.StaticPartitionsDefinition` (one per `space_id`) or `dg.DailyPartitionsDefinition` (one per day) on the `@dg.asset` decorator. Dagster's docs on partitions are authoritative, use `context7` to fetch the current syntax rather than copy-pasting from memory.

None of this is wired yet, start with a plain asset and add partitions later if needed.

---

## Common pitfalls

| Pitfall | Fix |
|---|---|
| `materialize(...)` fails with `KeyError: 'db'` | Your test did not pass the resource: `resources={"db": _StubResource()}`. |
| Resource stub fails Pydantic validation at construction | Your stub did not inherit from `DataWhiskSessionResource` or omitted `database_url`. Inherit and provide a dummy value. |
| Asset runs fine locally but queries return empty | Your `with db.session()` block uses the session after exiting. Move the `.all()` inside the block. |
| MLflow run shows no `space_id` tag | You called `mlflow.start_run()` directly instead of `run_for_space(space_id)` or `log_and_register_sklearn`. Always go through the helpers. |
| Asset takes 45 seconds to fail with a DB error after training completes | You kept the session open across training. Close it before long work; the pool timed out mid-run. |
| Dagster UI shows the asset but the code change is not reflected | Restart the webserver / daemon after adding a new asset. `docker compose restart dagster_webserver dagster_daemon`. |
| Tz-aware vs tz-naive comparison error | Strip tz before binding into the query. `dt.astimezone(timezone.utc).replace(tzinfo=None)`. |

---

## Cross-references

- [`architecture.md`](architecture.md) — the four-layer model
- [`adding-a-table.md`](adding-a-table.md) — add the ORM/DTO if the asset reads a new table
- [`adding-an-endpoint.md`](adding-an-endpoint.md) — the API-side counterpart
- `orchestration/assets/occupancy.py` — reference implementation
- `api/mlflow_utils.py` — MLflow helpers (import-safe from orchestration code)
