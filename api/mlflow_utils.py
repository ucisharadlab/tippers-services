from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import mlflow
import mlflow.pyfunc
import mlflow.sklearn
from mlflow.tracking import MlflowClient

DEFAULT_ALIAS = "production"
DEFAULT_MODEL_TYPE = "occupancy"


def model_name_for_space(space_id: int, model_type: str = DEFAULT_MODEL_TYPE) -> str:
    """
    Matching-table: space_id → Registered Model Name.

    Default convention is '{model_type}_space_{space_id}'. Override by
    subclassing ModelResolver and replacing `registered_name`.
    """
    return f"{model_type}_space_{space_id}"


@contextmanager
def run_for_space(
    space_id: int,
    extra_tags: dict[str, str] | None = None,
) -> Iterator[mlflow.ActiveRun]:
    """
    Start an MLflow run with `space_id` tagged. The tag is what makes runs
    searchable by tenant and what downstream tooling filters on.
    """
    tags = {"space_id": str(space_id)}
    if extra_tags:
        tags.update({k: str(v) for k, v in extra_tags.items()})
    with mlflow.start_run(tags=tags) as run:
        yield run


def log_and_register_sklearn(
    model: Any,
    space_id: int,
    model_type: str = DEFAULT_MODEL_TYPE,
    extra_tags: dict[str, str] | None = None,
) -> dict:
    """
    One-shot: start a tagged run, log a sklearn-flavored model, register
    it under the per-space name. Returns the registered name + version +
    run id. Promotion (alias assignment) is manual via MLflow UI.
    """
    name = model_name_for_space(space_id, model_type)
    with run_for_space(space_id, extra_tags) as run:
        result = mlflow.sklearn.log_model(
            sk_model=model,
            name="model",
            registered_model_name=name,
        )
    return {
        "registered_model_name": name,
        "version": str(result.registered_model_version),
        "run_id": run.info.run_id,
    }


class ModelResolver:
    """
    Space-aware loader. Given a space_id, returns a ready-to-predict pyfunc
    model loaded from the current `@{alias}` version in the MLflow registry.

    Callers only know their space_id; this class handles all MLflow URIs.
    """

    def __init__(
        self,
        alias: str = DEFAULT_ALIAS,
        model_type: str = DEFAULT_MODEL_TYPE,
        client: MlflowClient | None = None,
    ) -> None:
        self._alias = alias
        self._model_type = model_type
        self._client = client or MlflowClient()

    def registered_name(self, space_id: int) -> str:
        return model_name_for_space(space_id, self._model_type)

    def resolve_uri(self, space_id: int) -> str:
        return f"models:/{self.registered_name(space_id)}@{self._alias}"

    def resolve_version(self, space_id: int):
        """Return the MLflow ModelVersion currently pointed at by the alias."""
        return self._client.get_model_version_by_alias(
            self.registered_name(space_id), self._alias
        )

    def load(self, space_id: int):
        """Load-on-request; no caching in Phase 1."""
        return mlflow.pyfunc.load_model(self.resolve_uri(space_id))
