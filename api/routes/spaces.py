from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from api.deps import SessionDep
from datawhisk_shared.orm import Space

router = APIRouter(prefix="/services/spaces", tags=["spaces"])


@router.get("/{space_id}/children", response_model=list[int])
def get_child_spaces(space_id: int, session: SessionDep) -> list[int]:
    return list(
        session.scalars(
            select(Space.space_id)
            .where(Space.parent_space_id == space_id)
            .order_by(Space.space_id)
        ).all()
    )
