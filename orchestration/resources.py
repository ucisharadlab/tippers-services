from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from dagster import ConfigurableResource
from sqlalchemy.orm import Session

from datawhisk_shared import make_sessionmaker


class DataWhiskSessionResource(ConfigurableResource):
    database_url: str

    @contextmanager
    def session(self) -> Iterator[Session]:
        with make_sessionmaker(self.database_url)() as s:
            yield s
