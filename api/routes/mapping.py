from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.deps import SessionDep
from datawhisk_shared import ModelSpaceMappingRow
from datawhisk_shared.orm import ModelSpaceMapping

router = APIRouter(prefix="/services/mapping", tags=["mapping"])


@router.get("/{space_id}", response_model=ModelSpaceMappingRow)
def get_mapping(space_id: int, session: SessionDep) -> ModelSpaceMappingRow:
    row = session.get(ModelSpaceMapping, space_id)
    if row is None:
        raise HTTPException(404, f"no mapping for space_id={space_id}")
    return ModelSpaceMappingRow.model_validate(row)
