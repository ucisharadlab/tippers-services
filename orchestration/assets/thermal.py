from __future__ import annotations

from pathlib import Path

import dagster as dg
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

from orchestration.mlflow_utils import log_and_register_thermal, model_name_for_zone

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

EM_ZONE_DIR    = DATA_DIR / "em" / "zone"    / "full-features"
ETOTAL_ZONE_DIR = DATA_DIR / "ec" / "zone"   / "full-features"
EM_AP_DIR      = DATA_DIR / "em" / "wifi_ap" / "full-features"
ETOTAL_AP_DIR  = DATA_DIR / "ec" / "wifi_ap"

_EM_ZONE_COLS = [
    "zone_temp", "zone_temp_occ_clg_sp", "zone_temp_occ_htg_sp",
    "occupancy", "ambient_temperature", "day_of_the_week",
    "internal_neighbors_avg_zone_temp", "external_neighbors_avg_zone_temp",
    "internal_neighbors_avg_clg_sp",   "external_neighbors_avg_clg_sp",
    "internal_neighbors_avg_htg_sp",   "external_neighbors_avg_htg_sp",
    "internal_neighbors_avg_occupancy", "external_neighbors_avg_occupancy",
]

_EM_AP_COLS = [
    "ap_temp", "ap_temp_occ_clg_sp", "ap_temp_occ_htg_sp",
    "occupancy", "ambient_temperature", "start_hour", "month",
    "internal_zones_temp", "external_zones_temp",
    "internal_zones_clg_sp", "external_zones_clg_sp",
    "internal_zones_htg_sp", "external_zones_htg_sp",
]

_ETOTAL_ZONE_COLS = [
    "zone_temp", "zone_temp_occ_clg_sp", "zone_temp_occ_htg_sp",
    "temperature_to_cool", "occupancy", "ambient_temperature",
    "internal_neighbors_avg_zone_temp", "external_neighbors_avg_zone_temp",
    "internal_neighbors_avg_clg_sp",   "external_neighbors_avg_clg_sp",
    "internal_neighbors_avg_htg_sp",   "external_neighbors_avg_htg_sp",
    "internal_neighbors_avg_occupancy", "external_neighbors_avg_occupancy",
]

_ETOTAL_AP_COLS = ["ap_temp", "ap_temp_clg_sp"]


def _extract_zone_id(stem: str) -> str:
    return stem.removeprefix("zone_").removesuffix("_dataset")


def _build_features_em(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["start_hour"] = pd.to_datetime(df["start_timestamp"]).dt.hour
    df["is_weekend"] = (df["day_of_the_week"] >= 5).astype(int)
    cols = [c for c in _EM_ZONE_COLS if c in df.columns] + ["start_hour", "is_weekend"]
    out = df[cols].dropna(axis=1, how="all")
    return out.apply(pd.to_numeric, errors="coerce")


def _build_features_em_ap(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in _EM_AP_COLS if c in df.columns]
    return df[cols].dropna(axis=1, how="all").apply(pd.to_numeric, errors="coerce")


def _build_features_etotal(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in _ETOTAL_ZONE_COLS if c in df.columns]
    out = df[cols].dropna(axis=1, how="all")
    return out.apply(pd.to_numeric, errors="coerce")


def _build_features_etotal_ap(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in _ETOTAL_AP_COLS if c in df.columns]
    return df[cols].apply(pd.to_numeric, errors="coerce")


def _eval(model, X_test: pd.DataFrame, y_test: pd.Series) -> dict:
    if len(X_test) == 0:
        return {"r2": "n/a", "rmse": "n/a", "mae": "n/a"}
    preds = model.predict(X_test)
    return {
        "r2":   f"{r2_score(y_test, preds):.4f}",
        "rmse": f"{mean_squared_error(y_test, preds) ** 0.5:.4f}",
        "mae":  f"{mean_absolute_error(y_test, preds):.4f}",
    }


def _feature_importance(model, feature_names: list[str]) -> dict:
    importance = model.feature_importances_
    return dict(sorted(zip(feature_names, importance.tolist()), key=lambda x: x[1], reverse=True))


def _summarize(results: dict) -> dict:
    trained = [r for r in results.values() if r.get("status") == "trained"]
    skipped = [r for r in results.values() if r.get("status") != "trained"]
    r2_vals = [float(r["r2"]) for r in trained if r.get("r2", "n/a") != "n/a"]
    return {
        "total": len(results),
        "trained": len(trained),
        "skipped": len(skipped),
        "avg_holdout_r2": round(float(np.mean(r2_vals)), 4) if r2_vals else 0.0,
    }


@dg.asset(description="Trains Em (maintenance) models for all VAV zones and WiFi APs.", group_name="thermal")
def thermal_em_model(context) -> dg.MaterializeResult:
    results: dict[str, dict] = {}

    # ── Global model ──────────────────────────────────────────────────────────
    all_dfs = [pd.read_csv(f) for f in sorted(EM_ZONE_DIR.glob("zone_*_dataset.csv"))]
    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        X = _build_features_em(combined)
        y = combined["energy_usage_per_minute"]
        split = int(len(X) * 0.8)
        model = XGBRegressor(n_estimators=200, max_depth=4, random_state=42)
        model.fit(X.iloc[:split], y.iloc[:split])
        holdout = _eval(model, X.iloc[split:], y.iloc[split:])
        importance = _feature_importance(model, X.columns.tolist())
        name = model_name_for_zone("", "em", "global")
        log_and_register_thermal(model, name, extra_tags={**holdout},
                                 artifacts={"feature_importance": importance})
        results["__global__"] = {"status": "trained", **holdout}
        context.log.info(f"em global: {holdout}")

    # ── Local models (one per zone) ───────────────────────────────────────────
    for csv_path in sorted(EM_ZONE_DIR.glob("zone_*_dataset.csv")):
        zone_id = _extract_zone_id(csv_path.stem)
        df = pd.read_csv(csv_path)
        if len(df) < 20:
            results[zone_id] = {"status": "skipped — insufficient data", "rows": len(df)}
            continue
        X = _build_features_em(df)
        y = df["energy_usage_per_minute"]
        split = int(len(X) * 0.8)
        model = XGBRegressor(n_estimators=200, max_depth=4, random_state=42)
        model.fit(X.iloc[:split], y.iloc[:split])
        holdout = _eval(model, X.iloc[split:], y.iloc[split:])
        importance = _feature_importance(model, X.columns.tolist())
        name = model_name_for_zone(zone_id, "em", "local")
        log_and_register_thermal(model, name,
                                 extra_tags={"zone_id": zone_id, **holdout},
                                 artifacts={"feature_importance": importance})
        results[zone_id] = {"status": "trained", **holdout}

    context.log.info(f"em local: {len([r for r in results.values() if r.get('status')=='trained'])} trained")

    # ── Intermediate models (one per WiFi AP) ─────────────────────────────────
    for csv_path in sorted(EM_AP_DIR.glob("*_dataset.csv")):
        ap_id = csv_path.stem.replace("_dataset", "")
        df = pd.read_csv(csv_path)
        if len(df) < 20:
            results[f"ap:{ap_id}"] = {"status": "skipped — insufficient data"}
            continue
        X = _build_features_em_ap(df)
        y = df["energy_usage_per_minute"]
        split = int(len(X) * 0.8)
        model = XGBRegressor(n_estimators=200, max_depth=4, random_state=42)
        model.fit(X.iloc[:split], y.iloc[:split])
        holdout = _eval(model, X.iloc[split:], y.iloc[split:])
        name = model_name_for_zone(ap_id, "em", "intermediate")
        log_and_register_thermal(model, name, extra_tags={"ap_id": ap_id, **holdout})
        results[f"ap:{ap_id}"] = {"status": "trained", **holdout}

    context.log.info(f"em intermediate AP: done")
    return dg.MaterializeResult(metadata=_summarize(results))


@dg.asset(description="Trains Etotal (raw HVAC energy) models for all VAV zones and WiFi APs.", group_name="thermal")
def thermal_etotal_model(context) -> dg.MaterializeResult:
    results: dict[str, dict] = {}

    # ── Global model ──────────────────────────────────────────────────────────
    all_dfs = [pd.read_csv(f) for f in sorted(ETOTAL_ZONE_DIR.glob("zone_*_dataset.csv"))]
    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        X = _build_features_etotal(combined)
        y = combined["energy_usage_per_minute"]
        split = int(len(X) * 0.8)
        model = XGBRegressor(n_estimators=200, max_depth=4, random_state=42)
        model.fit(X.iloc[:split], y.iloc[:split])
        holdout = _eval(model, X.iloc[split:], y.iloc[split:])
        importance = _feature_importance(model, X.columns.tolist())
        name = model_name_for_zone("", "etotal", "global")
        log_and_register_thermal(model, name, extra_tags={**holdout},
                                 artifacts={"feature_importance": importance})
        results["__global__"] = {"status": "trained", **holdout}
        context.log.info(f"etotal global: {holdout}")

    # ── Local models ──────────────────────────────────────────────────────────
    for csv_path in sorted(ETOTAL_ZONE_DIR.glob("zone_*_dataset.csv")):
        zone_id = _extract_zone_id(csv_path.stem)
        df = pd.read_csv(csv_path)
        if len(df) < 20:
            results[zone_id] = {"status": "skipped — insufficient data", "rows": len(df)}
            continue
        X = _build_features_etotal(df)
        y = df["energy_usage_per_minute"]
        split = int(len(X) * 0.8)
        model = XGBRegressor(n_estimators=200, max_depth=4, random_state=42)
        model.fit(X.iloc[:split], y.iloc[:split])
        holdout = _eval(model, X.iloc[split:], y.iloc[split:])
        importance = _feature_importance(model, X.columns.tolist())
        name = model_name_for_zone(zone_id, "etotal", "local")
        log_and_register_thermal(model, name,
                                 extra_tags={"zone_id": zone_id, **holdout},
                                 artifacts={"feature_importance": importance})
        results[zone_id] = {"status": "trained", **holdout}

    context.log.info(f"etotal local: {len([r for r in results.values() if r.get('status')=='trained'])} trained")

    # ── Intermediate models (one per WiFi AP) ─────────────────────────────────
    for csv_path in sorted(ETOTAL_AP_DIR.glob("ap_*_dataset.csv")):
        ap_id = csv_path.stem.removeprefix("ap_").removesuffix("_dataset")
        df = pd.read_csv(csv_path)
        if len(df) < 10:
            results[f"ap:{ap_id}"] = {"status": "skipped — insufficient data"}
            continue
        X = _build_features_etotal_ap(df)
        y = df["energy_usage_per_minute"]
        split = int(len(X) * 0.8)
        model = XGBRegressor(n_estimators=200, max_depth=4, random_state=42)
        model.fit(X.iloc[:split], y.iloc[:split])
        holdout = _eval(model, X.iloc[split:], y.iloc[split:])
        name = model_name_for_zone(ap_id, "etotal", "intermediate")
        log_and_register_thermal(model, name, extra_tags={"ap_id": ap_id, **holdout})
        results[f"ap:{ap_id}"] = {"status": "trained", **holdout}

    context.log.info(f"etotal intermediate AP: done")
    return dg.MaterializeResult(metadata=_summarize(results))
