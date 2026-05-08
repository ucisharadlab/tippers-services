from __future__ import annotations

import tempfile
from pathlib import Path

import joblib
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from mlflow.tracking import MlflowClient

from api.mlflow_utils import DEFAULT_ALIAS, log_and_register_sklearn, model_name_for_space

router = APIRouter(prefix="/admin/models", tags=["admin"])


@router.post("/upload")
async def upload_model(
    space_id: int = Form(...),
    category: str = Form(default="occupancy", description="Model category / domain (was 'model_type')."),
    file: UploadFile = File(...),
) -> dict:
    """
    Phase 1: models are produced outside DataWhisk and uploaded here.

    Registers the uploaded sklearn/joblib model under the per-space
    Registered Model Name (`{category}_space_{space_id}`) with the
    run tagged `space_id={space_id}`. A new version is created; assign
    the `@production` alias in the MLflow UI to make it servable.
    """
    suffix = Path(file.filename or "model.joblib").suffix or ".joblib"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        try:
            model = joblib.load(tmp_path)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"could not load joblib: {e}") from e

        result = log_and_register_sklearn(
            model=model,
            space_id=space_id,
            model_type=category,
            extra_tags={"uploaded_filename": file.filename or "unknown"},
        )
        result["note"] = "Assign @production alias in MLflow UI to make this servable."
        return result
    finally:
        tmp_path.unlink(missing_ok=True)


@router.get("/{space_id}/versions")
async def list_model_versions(space_id: int) -> list[dict]:
    client = MlflowClient()
    name = model_name_for_space(space_id)
    try:
        versions = client.search_model_versions(
            f"name='{name}'", order_by=["version_number DESC"]
        )
    except Exception:
        return []

    production_version: str | None = None
    try:
        mv = client.get_model_version_by_alias(name, DEFAULT_ALIAS)
        production_version = mv.version
    except Exception:
        pass

    def _metrics(run_id: str) -> dict:
        try:
            tags = client.get_run(run_id).data.tags
            return {
                "rmse": float(tags["rmse"]) if "rmse" in tags else None,
                "mae": float(tags["mae"]) if "mae" in tags else None,
            }
        except Exception:
            return {"rmse": None, "mae": None}

    return [
        {
            "version": v.version,
            "is_production": v.version == production_version,
            "created_timestamp": v.creation_timestamp,
            "run_id": v.run_id,
            **_metrics(v.run_id),
        }
        for v in versions
    ]


@router.post("/{space_id}/set-production")
async def set_production_version(space_id: int, version: str) -> dict:
    client = MlflowClient()
    name = model_name_for_space(space_id)
    try:
        client.set_registered_model_alias(name, DEFAULT_ALIAS, version)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"registered_model_name": name, "version": version, "alias": DEFAULT_ALIAS}
