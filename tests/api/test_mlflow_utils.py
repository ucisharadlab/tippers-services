from __future__ import annotations

from unittest.mock import MagicMock, patch

from api.mlflow_utils import (
    ModelResolver,
    log_and_register_sklearn,
    model_name_for_space,
    run_for_space,
)


def test_model_name_convention():
    assert model_name_for_space(42) == "occupancy_space_42"
    assert model_name_for_space(7, model_type="thermal") == "thermal_space_7"


def test_run_for_space_tags_space_id():
    with patch("api.mlflow_utils.mlflow") as m:
        fake_run = MagicMock()
        m.start_run.return_value.__enter__.return_value = fake_run
        with run_for_space(space_id=42, extra_tags={"source": "upload"}):
            pass
        m.start_run.assert_called_once()
        tags = m.start_run.call_args.kwargs["tags"]
        assert tags["space_id"] == "42"
        assert tags["source"] == "upload"


def test_log_and_register_sklearn_uses_per_space_name():
    with patch("api.mlflow_utils.mlflow") as m:
        fake_run = MagicMock()
        fake_run.info.run_id = "r1"
        m.start_run.return_value.__enter__.return_value = fake_run
        fake_log = MagicMock()
        fake_log.registered_model_version = 4
        m.sklearn.log_model.return_value = fake_log

        result = log_and_register_sklearn(model=MagicMock(), space_id=42)

    assert result == {
        "registered_model_name": "occupancy_space_42",
        "version": "4",
        "run_id": "r1",
    }
    kwargs = m.sklearn.log_model.call_args.kwargs
    assert kwargs["registered_model_name"] == "occupancy_space_42"
    assert m.start_run.call_args.kwargs["tags"]["space_id"] == "42"


def test_resolver_builds_alias_uri():
    r = ModelResolver(alias="production", client=MagicMock())
    assert r.resolve_uri(42) == "models:/occupancy_space_42@production"
    assert r.registered_name(42) == "occupancy_space_42"


def test_resolver_load_uses_pyfunc():
    with patch("api.mlflow_utils.mlflow.pyfunc") as pyfunc:
        r = ModelResolver(client=MagicMock())
        r.load(42)
        pyfunc.load_model.assert_called_once_with("models:/occupancy_space_42@production")


def test_resolver_version_lookup_via_client():
    client = MagicMock()
    client.get_model_version_by_alias.return_value = MagicMock(version=7)
    r = ModelResolver(client=client)
    mv = r.resolve_version(42)
    client.get_model_version_by_alias.assert_called_once_with("occupancy_space_42", "production")
    assert mv.version == 7
