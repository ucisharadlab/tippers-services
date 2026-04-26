from __future__ import annotations
from pathlib import Path
 
from datetime import datetime, timedelta, timezone
 
import dagster as dg
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sqlalchemy import select
from xgboost import XGBRegressor
 
from orchestration.mlflow_utils import DEFAULT_ALIAS, log_and_register_sklearn
from datawhisk_shared import OccupancyRow
from datawhisk_shared.mapping import upsert_model_mapping
from datawhisk_shared.orm import Occupancy
from orchestration.resources import DataWhiskSessionResource

BY_ROOM_DIR = Path(__file__).resolve().parents[2] / "by_room_data"
CSV_COLUMNS = ["spaceid", "starttime", "endtime", "occupancy"]

def _load_csv(path: Path) -> pd.DataFrame:
    """Read one by-room CSV into a DataFrame with correct dtypes."""
    df = pd.read_csv(path, header=0)
    df.columns = CSV_COLUMNS
    df["starttime"] = pd.to_datetime(df["starttime"])
    df["endtime"] = pd.to_datetime(df["endtime"])
    return df


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Convert OccupancyRow DTOs into the feature DataFrame the model expects."""
    df = df.copy()
    df["hour"] = df["starttime"].dt.hour
    df["dayofweek"] = df["starttime"].dt.dayofweek  # 0=Monday
    df["is_weekend"] = df["dayofweek"].isin([5, 6]).astype(int)
    return df[["hour", "dayofweek", "is_weekend"]]


def _train_for_space(
    df: pd.DataFrame,
    space_id: int,
    context: dg.AssetExecutionContext,
) -> dict:
    """
    Train one XGBClassifier for a single space_id and log it to MLflow.
    Returns a dict of metadata for Dagster's MaterializeResult.
    """
    if len(df) < 10:
        context.log.warning(
            f"space_id={space_id}: only {len(df)} rows — skipping (need ≥ 10)"
        )
        return {"rows": len(df), "status": "skipped — insufficient data"}
 
    X = _build_features(df)
    y = df["occupancy"].values
 
    # Temporal split — preserve time ordering
    split = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y[:split], y[split:]
 
    model = XGBRegressor(random_state=42)
    model.fit(X_train, y_train)
 
    y_pred = model.predict(X_test)
    rmse = mean_squared_error(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    context.log.info(f"space_id={space_id}: rmse={rmse:.4f} mae={mae:.4f}")
 
    mlflow_result = log_and_register_sklearn(
        model=model,
        space_id=space_id,
        model_type="occupancy",
        extra_tags={
            "training_rows": str(len(X_train)),
            "test_rows": str(len(X_test)),
            "rmse": f"{rmse:.4f}",
            "mae": f"{mae:.4f}",
        },
    )
 
    return {
        "rows": len(df),
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "rmse": round(rmse, 4),
        "mae": round(mae, 4),
        "mlflow_model": mlflow_result["registered_model_name"],
        "mlflow_version": mlflow_result["version"],
        "mlflow_run_id": mlflow_result["run_id"],
        "status": "trained",
    }





class OccupancyTrainConfig(dg.Config):
    space_id: int = 1
    lookback_days: int = 30


@dg.asset(
    description="Occupancy model asset. Pulls training data; training + MLflow logging are Gabriel's placeholder.",
    group_name="occupancy",
)
def occupancy_model(context, db: DataWhiskSessionResource) -> dg.MaterializeResult:
    csv_files = sorted(BY_ROOM_DIR.glob("*.csv"))
    context.log.info(f"found {len(csv_files)} CSV files in {BY_ROOM_DIR}")
 
    results: dict[int, dict] = {}
 
    for csv_path in csv_files:
        df = _load_csv(csv_path)
 
        # space_id comes from the first column; grab the first value
        space_id = int(df["spaceid"].iloc[0])
        context.log.info(f"training space_id={space_id} from {csv_path.name}")
 
        results[space_id] = _train_for_space(df, space_id, context)

    with db.session() as session:
        for space_id, r in results.items():
            if r["status"] != "trained":
                continue
            uri = f"models:/{r['mlflow_model']}@{DEFAULT_ALIAS}"
            upsert_model_mapping(
                session,
                space_id=space_id,
                last_run_id=context.run_id,
                occupancy_model_uri=uri,
            )

    trained = [s for s, r in results.items() if r["status"] == "trained"]
    skipped = [s for s, r in results.items() if r["status"] != "trained"]
    avg_rmse = (
        sum(results[s]["rmse"] for s in trained) / len(trained) if trained else 0.0
    )
 
    context.log.info(
        f"done — trained={len(trained)}, skipped={len(skipped)}, avg_rmse={avg_rmse:.4f}"
    )
 
    return dg.MaterializeResult(
        metadata={
            "total_spaces": len(results),
            "trained": len(trained),
            "skipped": len(skipped),
            "avg_rmse": round(avg_rmse, 4),
            "trained_space_ids": str(sorted(trained)),
            "skipped_space_ids": str(sorted(skipped)),
        }
    )
