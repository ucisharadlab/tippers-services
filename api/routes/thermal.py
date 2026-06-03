from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import mlflow
import mlflow.pyfunc
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from api.deps import SessionDep
from mlflow.exceptions import MlflowException
from sqlalchemy import select

from api.deps import _sessionmaker as _get_sessionmaker
from api.mlflow_utils import ModelResolver, model_name_for_zone
from datawhisk_shared.orm import ZoneVavMapping

log = logging.getLogger(__name__)

router = APIRouter(prefix="/services/thermal", tags=["thermal"])

COEFFICIENTS_PATH = Path(__file__).resolve().parents[2] / "data/thermal/zone_thermal_coefficients.csv"

_EM_ZONE_FEATURES = [
    "zone_temp", "zone_temp_occ_clg_sp", "zone_temp_occ_htg_sp",
    "occupancy", "ambient_temperature", "day_of_the_week",
    "internal_neighbors_avg_zone_temp", "external_neighbors_avg_zone_temp",
    "internal_neighbors_avg_clg_sp",   "external_neighbors_avg_clg_sp",
    "internal_neighbors_avg_htg_sp",   "external_neighbors_avg_htg_sp",
    "internal_neighbors_avg_occupancy", "external_neighbors_avg_occupancy",
    "start_hour", "is_weekend",
]

_ETOTAL_ZONE_FEATURES = [
    "zone_temp", "zone_temp_occ_clg_sp", "zone_temp_occ_htg_sp",
    "temperature_to_cool", "occupancy", "ambient_temperature",
    "internal_neighbors_avg_zone_temp", "external_neighbors_avg_zone_temp",
    "internal_neighbors_avg_clg_sp",   "external_neighbors_avg_clg_sp",
    "internal_neighbors_avg_htg_sp",   "external_neighbors_avg_htg_sp",
    "internal_neighbors_avg_occupancy", "external_neighbors_avg_occupancy",
]


def _build_zone_to_sensoria_id() -> dict[str, int]:
    with _get_sessionmaker()() as session:
        rows = session.execute(
            select(ZoneVavMapping.vav_name, ZoneVavMapping.space_id)
        ).all()
    zone_to_sensoria: dict[str, int] = {}
    for vav_name, space_id in rows:
        zone_to_sensoria.setdefault(vav_name, space_id)
    return zone_to_sensoria


def _build_zone_to_ap() -> dict[str, list[str]]:
    with _get_sessionmaker()() as session:
        rows = session.execute(
            select(ZoneVavMapping.vav_name, ZoneVavMapping.wifi_ap)
        ).all()
    zone_to_aps: dict[str, list[str]] = {}
    for vav_name, wifi_ap in rows:
        zone_to_aps.setdefault(vav_name, []).append(wifi_ap)
    return zone_to_aps


_ZONE_TO_SENSORIA_ID: dict[str, int] | None = None
_ZONE_TO_AP: dict[str, list[str]] | None    = None
_coeff_cache: dict | None                   = None
_occ_resolver = ModelResolver(model_type="occupancy", alias="production")


def _get_zone_to_sensoria_id() -> dict[str, int]:
    global _ZONE_TO_SENSORIA_ID
    if _ZONE_TO_SENSORIA_ID is None:
        _ZONE_TO_SENSORIA_ID = _build_zone_to_sensoria_id()
    return _ZONE_TO_SENSORIA_ID


def _get_zone_to_ap() -> dict[str, list[str]]:
    global _ZONE_TO_AP
    if _ZONE_TO_AP is None:
        _ZONE_TO_AP = _build_zone_to_ap()
    return _ZONE_TO_AP


def _load_coefficients() -> dict:
    global _coeff_cache
    if _coeff_cache is None:
        df = pd.read_csv(COEFFICIENTS_PATH).set_index("vav_zone")
        _coeff_cache = df.to_dict(orient="index")
    return _coeff_cache


def _load_thermal_model(name: str) -> Any:
    return mlflow.pyfunc.load_model(f"models:/{name}@production")


def _get_occupancy(zone_id: str, at: datetime) -> tuple[float, int | None, bool]:
    """Return (occupancy, sensoria_spaceid_or_None, is_fallback)."""
    sensoria_id = _get_zone_to_sensoria_id().get(zone_id)
    if sensoria_id is None:
        return 0.0, None, True
    try:
        model, _ = _occ_resolver.load(sensoria_id)
        feat = pd.DataFrame([{
            "hour_sin":     math.sin(2 * math.pi * at.hour / 24),
            "hour_cos":     math.cos(2 * math.pi * at.hour / 24),
            "dow_sin":      math.sin(2 * math.pi * at.weekday() / 7),
            "dow_cos":      math.cos(2 * math.pi * at.weekday() / 7),
            "month":        at.month,
            "week_of_year": at.isocalendar().week,
            "is_weekend":   1 if at.weekday() >= 5 else 0,
        }])
        occ = float(model.predict(feat)[0])
        return occ, sensoria_id, False
    except MlflowException:
        return 0.0, sensoria_id, True


def _em_features(zone_temp: float, clg_setpoint: float, htg_setpoint: float,
                 occupancy: float, ambient_temp: float, at: datetime) -> pd.DataFrame:
    row = {c: 0.0 for c in _EM_ZONE_FEATURES}
    row["zone_temp"]             = zone_temp
    row["zone_temp_occ_clg_sp"]  = clg_setpoint
    row["zone_temp_occ_htg_sp"]  = htg_setpoint
    row["occupancy"]             = occupancy
    row["ambient_temperature"]   = ambient_temp
    row["day_of_the_week"]       = at.weekday()
    row["start_hour"]            = at.hour
    row["is_weekend"]            = 1 if at.weekday() >= 5 else 0
    return pd.DataFrame([row])


def _etotal_features(zone_temp: float, clg_setpoint: float,
                     occupancy: float, ambient_temp: float, at: datetime) -> pd.DataFrame:
    row = {c: 0.0 for c in _ETOTAL_ZONE_FEATURES}
    row["zone_temp"]            = zone_temp
    row["zone_temp_occ_clg_sp"] = clg_setpoint
    row["temperature_to_cool"]  = zone_temp - clg_setpoint
    row["occupancy"]            = occupancy
    row["ambient_temperature"]  = ambient_temp
    return pd.DataFrame([row])


def _resolve_model_name(zone_id: str, model_type: str, granularity: str) -> tuple[str, str | None]:
    """Return (model_name, ap_id_used_or_None). Raises HTTPException on failure."""
    if granularity == "global":
        return model_name_for_zone("", model_type, "global"), None
    if granularity == "local":
        return model_name_for_zone(zone_id, model_type, "local"), None
    if granularity == "intermediate":
        aps = _get_zone_to_ap().get(zone_id, [])
        if not aps:
            raise HTTPException(422, f"No WiFi APs mapped to zone {zone_id!r}")
        from mlflow.tracking import MlflowClient
        client = MlflowClient()
        for ap in aps:
            name = model_name_for_zone(ap, model_type, "intermediate")
            try:
                client.get_model_version_by_alias(name, "production")
                return name, ap
            except MlflowException:
                continue
        raise HTTPException(404, f"No @production intermediate model found for zone {zone_id!r}")
    raise HTTPException(422, f"Unknown granularity {granularity!r}; use local, global, or intermediate")


@router.get("/zones", response_model=list[str])
def list_zones(session: SessionDep) -> list[str]:
    """Return distinct VAV names from zone_vav_mapping, sorted alphabetically."""
    rows = session.execute(
        text("SELECT DISTINCT vav_name FROM zone_vav_mapping ORDER BY vav_name")
    ).fetchall()
    return [row[0] for row in rows]


@router.get("/{zone_id}/coefficients")
def get_coefficients(zone_id: str) -> dict:
    """Return alpha, beta thermal coefficients for a VAV zone."""
    coeffs = _load_coefficients()
    if zone_id not in coeffs:
        raise HTTPException(404, f"No thermal coefficients for zone {zone_id!r}")
    row = coeffs[zone_id]
    return {"zone_id": zone_id, **row}


@router.get("/{zone_id}/predict")
def predict_thermal(
    zone_id: str,
    model_type: str = Query("em", description="em, etotal, or ec"),
    granularity: str = Query("local", description="local, global, or intermediate"),
    zone_temp: float = Query(...),
    clg_setpoint: float = Query(...),
    htg_setpoint: float | None = Query(default=None),
    ambient_temp: float = Query(...),
    at: datetime | None = Query(default=None, description="ISO-8601 timestamp; defaults to now (UTC)"),
) -> dict:
    """Predict thermal energy for a VAV zone. Occupancy is fetched from the occupancy model."""
    if model_type not in ("em", "etotal", "ec"):
        raise HTTPException(422, "model_type must be em, etotal, or ec")

    ts = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    occupancy, sensoria_id, occ_fallback = _get_occupancy(zone_id, ts)

    response_base: dict = {
        "zone_id": zone_id,
        "model_type": model_type,
        "granularity": granularity,
        "occupancy_used": occupancy,
        "occupancy_space_id": sensoria_id,
    }
    if occ_fallback:
        response_base["occupancy_fallback"] = True

    if model_type == "ec":
        em_name, ap_id = _resolve_model_name(zone_id, "em", granularity)
        etotal_name, _ = _resolve_model_name(zone_id, "etotal", granularity)
        try:
            em_model     = _load_thermal_model(em_name)
            etotal_model = _load_thermal_model(etotal_name)
        except MlflowException as e:
            raise HTTPException(404, f"Model not found: {e}") from e

        eff_htg = htg_setpoint if htg_setpoint is not None else clg_setpoint - 4.0
        em_feats     = _em_features(zone_temp, clg_setpoint, eff_htg, occupancy, ambient_temp, ts)
        etotal_feats = _etotal_features(zone_temp, clg_setpoint, occupancy, ambient_temp, ts)

        em_pred     = float(em_model.predict(em_feats)[0])
        etotal_pred = float(etotal_model.predict(etotal_feats)[0])
        ec_pred     = max(0.0, etotal_pred - em_pred)

        resp = {**response_base,
                "predicted_energy_kwh_per_min": ec_pred,
                "etotal_raw": etotal_pred,
                "em_raw": em_pred,
                "model_version": None}
        if granularity == "intermediate" and ap_id:
            resp["ap_id_used"] = ap_id
        return resp

    model_name, ap_id = _resolve_model_name(zone_id, model_type, granularity)
    try:
        model = _load_thermal_model(model_name)
    except MlflowException as e:
        raise HTTPException(404, f"Model not found (assign @production alias in MLflow): {e}") from e

    if model_type == "em":
        eff_htg = htg_setpoint if htg_setpoint is not None else clg_setpoint - 4.0
        feats = _em_features(zone_temp, clg_setpoint, eff_htg, occupancy, ambient_temp, ts)
    else:
        feats = _etotal_features(zone_temp, clg_setpoint, occupancy, ambient_temp, ts)

    prediction = float(model.predict(feats)[0])
    resp = {**response_base,
            "predicted_energy_kwh_per_min": prediction,
            "model_version": None}
    if granularity == "intermediate" and ap_id:
        resp["ap_id_used"] = ap_id
    return resp


@router.get("/{zone_id}/predict/range")
def predict_thermal_range(
    zone_id: str,
    model_type: str = Query("em", description="em, etotal, or ec"),
    granularity: str = Query("local", description="local, global, or intermediate"),
    zone_temp: float = Query(...),
    clg_setpoint: float = Query(...),
    htg_setpoint: float | None = Query(default=None),
    ambient_temp: float = Query(...),
    start: datetime = Query(..., description="ISO-8601 start timestamp"),
    end: datetime = Query(..., description="ISO-8601 end timestamp"),
    interval_minutes: int = Query(60, description="Step size in minutes"),
) -> list[dict]:
    """Predict thermal energy for a VAV zone over a time range at fixed intervals."""
    if model_type not in ("em", "etotal", "ec"):
        raise HTTPException(422, "model_type must be em, etotal, or ec")
    if interval_minutes < 1:
        raise HTTPException(422, "interval_minutes must be at least 1")

    start_utc = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)
    if end_utc <= start_utc:
        raise HTTPException(422, "end must be after start")

    n_points = int((end_utc - start_utc).total_seconds() / 60) // interval_minutes + 1
    if n_points > 1440:
        raise HTTPException(422, f"Range produces {n_points} points; maximum is 1440. Increase interval_minutes or shorten the range.")

    if model_type == "ec":
        em_name, ap_id = _resolve_model_name(zone_id, "em", granularity)
        etotal_name, _ = _resolve_model_name(zone_id, "etotal", granularity)
        try:
            em_model = _load_thermal_model(em_name)
            etotal_model = _load_thermal_model(etotal_name)
        except MlflowException as e:
            raise HTTPException(404, f"Model not found: {e}") from e
    else:
        model_name, ap_id = _resolve_model_name(zone_id, model_type, granularity)
        try:
            model = _load_thermal_model(model_name)
        except MlflowException as e:
            raise HTTPException(404, f"Model not found (assign @production alias in MLflow): {e}") from e

    results = []
    ts = start_utc
    while ts <= end_utc:
        occupancy, _, occ_fallback = _get_occupancy(zone_id, ts)
        entry: dict = {"timestamp": ts.isoformat(), "occupancy_used": occupancy}
        if occ_fallback:
            entry["occupancy_fallback"] = True

        if model_type == "ec":
            eff_htg = htg_setpoint if htg_setpoint is not None else clg_setpoint - 4.0
            em_pred = float(em_model.predict(_em_features(zone_temp, clg_setpoint, eff_htg, occupancy, ambient_temp, ts))[0])
            etotal_pred = float(etotal_model.predict(_etotal_features(zone_temp, clg_setpoint, occupancy, ambient_temp, ts))[0])
            entry["predicted_energy_kwh_per_min"] = max(0.0, etotal_pred - em_pred)
            entry["etotal_raw"] = etotal_pred
            entry["em_raw"] = em_pred
        elif model_type == "em":
            eff_htg = htg_setpoint if htg_setpoint is not None else clg_setpoint - 4.0
            entry["predicted_energy_kwh_per_min"] = float(model.predict(_em_features(zone_temp, clg_setpoint, eff_htg, occupancy, ambient_temp, ts))[0])
        else:
            entry["predicted_energy_kwh_per_min"] = float(model.predict(_etotal_features(zone_temp, clg_setpoint, occupancy, ambient_temp, ts))[0])

        results.append(entry)
        ts += timedelta(minutes=interval_minutes)

    return results
