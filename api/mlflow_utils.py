from __future__ import annotations

from contextlib import contextmanager
from threading import Lock
from typing import Any, Iterator

import mlflow
import mlflow.pyfunc
import mlflow.sklearn
from mlflow.entities.model_registry import ModelVersion
from mlflow.tracking import MlflowClient

DEFAULT_ALIAS = "production"
DEFAULT_MODEL_TYPE = "occupancy"


def model_name_for_zone(zone_id: str, model_type: str, granularity: str = "local") -> str:
    """e.g. model_name_for_zone('VAV1.10', 'em', 'local') → 'em_local_VAV1_10'"""
    if granularity == "global":
        return f"{model_type}_global"
    safe = zone_id.replace(".", "_").replace("-", "_")
    return f"{model_type}_{granularity}_{safe}"


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
    Space-aware search + load for the MLflow registry.

    Inference flow per request:
      1. Search: ask the registry which ModelVersion the `@{alias}` points at
         for this space's registered model (`{model_type}_space_{space_id}`).
      2. Load: fetch that exact version's pyfunc, cached by (name, version)
         so alias flips are picked up on the next request but repeat calls
         within the same version skip the artifact fetch.
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
        self._cache: dict[tuple[str, str], Any] = {}
        self._lock = Lock()

    def registered_name(self, space_id: int) -> str:
        return model_name_for_space(space_id, self._model_type)

    def resolve_uri(self, space_id: int) -> str:
        return f"models:/{self.registered_name(space_id)}@{self._alias}"

    def resolve_version(self, space_id: int) -> ModelVersion:
        """Return the ModelVersion currently pointed at by the alias.
        Raises MlflowException(RESOURCE_DOES_NOT_EXIST) if the model isn't
        registered or the alias isn't assigned."""
        return self._client.get_model_version_by_alias(
            self.registered_name(space_id), self._alias
        )

    def search_versions(self, space_id: int) -> list[ModelVersion]:
        """All versions of a space's registered model, newest first — used
        when diagnosing 'why isn't my promotion visible?'."""
        name = self.registered_name(space_id)
        return self._client.search_model_versions(
            f"name='{name}'", order_by=["version_number DESC"]
        )

    def list_spaces(self) -> list[int]:
        """Space ids that currently have a `@{alias}` version registered.
        Scans registered models whose name matches the per-space convention."""
        prefix = f"{self._model_type}_space_"
        spaces: list[int] = []
        for rm in self._client.search_registered_models(
            filter_string=f"name LIKE '{prefix}%'"
        ):
            try:
                self._client.get_model_version_by_alias(rm.name, self._alias)
            except Exception:
                continue
            try:
                spaces.append(int(rm.name[len(prefix):]))
            except ValueError:
                continue
        return sorted(spaces)

    def load(self, space_id: int) -> tuple[Any, ModelVersion]:
        """Resolve alias → version (search), then load pyfunc (load).
        Returns (pyfunc_model, version_metadata). Cached per (name, version)."""
        name = self.registered_name(space_id)
        mv = self._client.get_model_version_by_alias(name, self._alias)
        key = (name, mv.version)
        with self._lock:
            model = self._cache.get(key)
            if model is None:
                model = mlflow.pyfunc.load_model(f"models:/{name}/{mv.version}")
                self._cache[key] = model
        return model, mv

    def invalidate(self, space_id: int | None = None) -> None:
        """Drop cached pyfuncs. Without an arg, clears everything; with a
        space_id, only evicts that space's entries."""
        with self._lock:
            if space_id is None:
                self._cache.clear()
                return
            name = self.registered_name(space_id)
            self._cache = {k: v for k, v in self._cache.items() if k[0] != name}


occupancy_resolver = ModelResolver(model_type=DEFAULT_MODEL_TYPE, alias=DEFAULT_ALIAS)
