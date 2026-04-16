from __future__ import annotations

import tempfile
from pathlib import Path

import joblib
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.mlflow_utils import log_and_register_sklearn

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
