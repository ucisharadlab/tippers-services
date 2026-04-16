from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ARRAY, DateTime, Integer, JSON, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from datawhisk_shared.base import Base


class Space(Base):
    __tablename__ = "space"

    space_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    space_name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_space_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coordinate_system_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    space_shape: Mapped[str | None] = mapped_column(Text, nullable=True)
    extent: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    space_type_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gps_extent: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    radius: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    # vertices/gps_vertices are Postgres `coordinate[]` (composite-type arrays).
    # SQLAlchemy has no native type for user-defined composite arrays; ARRAY(Text)
    # is a placeholder so the column exists on the mapper. Reading these through
    # the ORM may produce raw strings or fail depending on psycopg version — use
    # raw SQL or a custom TypeDecorator if you need to consume them.
    vertices: Mapped[list[Any] | None] = mapped_column(ARRAY(Text), nullable=True)
    gps_vertices: Mapped[list[Any] | None] = mapped_column(ARRAY(Text), nullable=True)


class Occupancy(Base):
    __tablename__ = "occupancy"

    spaceid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starttime: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    endtime: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    occupancy: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # The real table has no primary key; give the mapper a virtual identity so
    # ORM queries/identity-map work. This does NOT emit DDL — safe against the
    # existing Tippers schema.
    __mapper_args__ = {
        "primary_key": [spaceid, starttime, endtime],
    }
