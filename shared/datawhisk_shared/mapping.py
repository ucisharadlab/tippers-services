from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from datawhisk_shared.orm import ModelSpaceMapping


def upsert_model_mapping(
    session: Session,
    *,
    space_id: int,
    last_run_id: str,
    occupancy_model_uri: str | None = None,
    thermal_model_uri: str | None = None,
    last_trained: datetime | None = None,
) -> ModelSpaceMapping:
    """Insert or update the mapping row for `space_id`.

    Only non-None URI fields are written, so an occupancy training run won't
    clobber a previously-recorded thermal URI (and vice versa). Commits the
    session before returning.
    """
    row = session.get(ModelSpaceMapping, space_id)
    trained_at = last_trained or datetime.now(tz=timezone.utc)

    if row is None:
        row = ModelSpaceMapping(
            space_id=space_id,
            occupancy_model_uri=occupancy_model_uri,
            thermal_model_uri=thermal_model_uri,
            last_trained=trained_at,
            last_run_id=last_run_id,
        )
        session.add(row)
    else:
        if occupancy_model_uri is not None:
            row.occupancy_model_uri = occupancy_model_uri
        if thermal_model_uri is not None:
            row.thermal_model_uri = thermal_model_uri
        row.last_trained = trained_at
        row.last_run_id = last_run_id

    session.commit()
    return row
