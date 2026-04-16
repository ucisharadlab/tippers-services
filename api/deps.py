from __future__ import annotations

import os
from functools import lru_cache
from typing import Annotated, Generator

from fastapi import Depends
from sqlalchemy.orm import Session, sessionmaker

from datawhisk_shared import make_sessionmaker


@lru_cache(maxsize=1)
def _sessionmaker() -> sessionmaker[Session]:
    return make_sessionmaker(os.environ["DATABASE_URL"])


def get_session() -> Generator[Session, None, None]:
    with _sessionmaker()() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
