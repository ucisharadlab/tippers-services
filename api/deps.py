from __future__ import annotations

import os
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from datawhisk_shared import DataWhiskDB


@lru_cache(maxsize=1)
def get_db() -> DataWhiskDB:
    return DataWhiskDB(os.environ["DATABASE_URL"])


DBDep = Annotated[DataWhiskDB, Depends(get_db)]
