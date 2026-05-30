from __future__ import annotations

import logging
from datetime import date as _Date, datetime, timedelta, timezone
from typing import Any

import pulp
from fastapi import APIRouter, HTTPException, Query
from mlflow.exceptions import MlflowException

from api.routes.thermal import (
    _em_features,
    _etotal_features,
    _get_occupancy,
    _load_coefficients,
    _load_thermal_model,
    _resolve_model_name,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/services/thermal", tags=["thermal"])

_TOU_PEAK_RATE = 0.50   # $/kWh: 22:00–04:00 UTC (3 pm–9 pm PDT)
_TOU_OFF_RATE  = 0.18   # $/kWh: all other hours


def _tou_price(ts: datetime) -> float:
    h = ts.hour
    return _TOU_PEAK_RATE if (h >= 22 or h < 4) else _TOU_OFF_RATE


def _load_zone_coefficients(zone_id: str, interval_minutes: int) -> tuple[float, float]:
    """Return (alpha, beta) scaled to interval_minutes, floored to 0.05."""
    coeffs = _load_coefficients()
    if zone_id in coeffs:
        row = coeffs[zone_id]
    else:
        log.warning("No thermal coefficients for zone %r; using __fallback__", zone_id)
        if "__fallback__" not in coeffs:
            raise HTTPException(500, "No __fallback__ row in zone_thermal_coefficients.csv")
        row = coeffs["__fallback__"]
    scale = interval_minutes / 15.0
    return (
        max(abs(row["alpha"]) * scale, 0.05),
        max(abs(row["beta"])  * scale, 0.05),
    )


def _optimize_single_day(
    zone_id: str,
    zone_temp: float,
    clg_setpoint: float,
    eff_htg: float,
    ambient_temp: float,
    alpha: float,
    beta: float,
    em_model: Any,
    etotal_model: Any,
    target_date: _Date,
    interval_minutes: int,
) -> dict:
    """Core MILP optimizer for one planning day. Returns a day-result dict (no zone_id key)."""
    noon = datetime(target_date.year, target_date.month, target_date.day, 12, 0, tzinfo=timezone.utc)
    noon_occ, _, _ = _get_occupancy(zone_id, noon)
    em_pred     = float(em_model.predict(_em_features(zone_temp, clg_setpoint, eff_htg, noon_occ, ambient_temp, noon))[0])
    etotal_pred = float(etotal_model.predict(_etotal_features(zone_temp, clg_setpoint, noon_occ, ambient_temp, noon))[0])
    Cmaintain = max(em_pred,    0.0) * interval_minutes
    Ccool     = max(etotal_pred, 0.0) * interval_minutes

    N = 1440 // interval_minutes
    day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, tzinfo=timezone.utc)

    timestamps:   list[datetime] = []
    occupancies:  list[float]    = []
    tou_prices:   list[float]    = []
    comfort_caps: list[float]    = []

    cum_occ   = 0   # occupied intervals seen before t
    cum_unocc = 0   # unoccupied intervals seen before t
    for t in range(N):
        ts = day_start + timedelta(minutes=t * interval_minutes)
        raw_occ, _, _ = _get_occupancy(zone_id, ts)
        occ = max(raw_occ, 0.0)
        timestamps.append(ts)
        occupancies.append(occ)
        tou_prices.append(_tou_price(ts))
        if occ > 0:
            # Cap based on actual occupied/unoccupied history so the optimizer can
            # go "off" during unoccupied windows without violating caps at the
            # next occupied interval.
            min_achievable = zone_temp - beta * cum_occ + alpha * cum_unocc
            comfort_caps.append(max(min_achievable, clg_setpoint + 2.0))
            cum_occ += 1
        else:
            comfort_caps.append(999.0)
            cum_unocc += 1

    prob = pulp.LpProblem(f"hvac_{target_date}", pulp.LpMinimize)
    c = [pulp.LpVariable(f"c_{t}", cat="Binary") for t in range(N)]
    m = [pulp.LpVariable(f"m_{t}", cat="Binary") for t in range(N)]
    o = [pulp.LpVariable(f"o_{t}", cat="Binary") for t in range(N)]
    T = [pulp.LpVariable(f"T_{t}", lowBound=clg_setpoint - 4.0, upBound=95.0) for t in range(N)]

    prob += pulp.lpSum(tou_prices[t] * (c[t] * Ccool + m[t] * Cmaintain) for t in range(N))

    for t in range(N):
        prob += c[t] + m[t] + o[t] == 1
        prev_T = zone_temp if t == 0 else T[t - 1]
        prob += T[t] == prev_T - beta * c[t] + alpha * o[t]
        if occupancies[t] > 0:
            prob += T[t] <= comfort_caps[t]

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    status = pulp.LpStatus[prob.status]
    if status != "Optimal":
        return {
            "solver_status":            status,
            "total_optimized_cost_usd": 0.0,
            "total_naive_cost_usd":     0.0,
            "savings_pct":              0.0,
            "interval_minutes":         interval_minutes,
            "intervals":                [],
        }

    naive_cost = 0.0
    naive_T = zone_temp
    naive_temps: list[float] = []
    for t in range(N):
        if occupancies[t] > 0:
            if naive_T > clg_setpoint + 2:
                naive_T -= beta
                naive_cost += tou_prices[t] * Ccool
            else:
                naive_cost += tou_prices[t] * Cmaintain
        else:
            naive_T += alpha
        naive_temps.append(naive_T)

    intervals = []
    total_opt_cost = 0.0
    for t in range(N):
        cv = round(pulp.value(c[t]) or 0)
        mv = round(pulp.value(m[t]) or 0)

        if cv == 1:
            state  = "cooling"
            energy = Ccool
        elif mv == 1:
            state  = "maintaining"
            energy = Cmaintain
        else:
            state  = "off"
            energy = 0.0

        interval_cost  = tou_prices[t] * energy
        total_opt_cost += interval_cost

        intervals.append({
            "timestamp":         timestamps[t].isoformat(),
            "state":             state,
            "temperature":       round(pulp.value(T[t]) or 0.0, 4),
            "naive_temperature": round(naive_temps[t], 4),
            "energy_kwh":        round(energy, 6),
            "interval_cost_usd": round(interval_cost, 6),
            "tou_price":         tou_prices[t],
            "occupancy":         occupancies[t],
        })

    savings_pct = (naive_cost - total_opt_cost) / naive_cost * 100 if naive_cost > 0 else 0.0

    return {
        "solver_status":            status,
        "total_optimized_cost_usd": round(total_opt_cost, 4),
        "total_naive_cost_usd":     round(naive_cost, 4),
        "savings_pct":              round(savings_pct, 2),
        "interval_minutes":         interval_minutes,
        "intervals":                intervals,
    }


@router.get("/{zone_id}/optimize/range")
def optimize_schedule_range(
    zone_id: str,
    granularity: str = Query("local", description="local, global, or intermediate"),
    zone_temp: float = Query(..., description="Initial zone temperature °F for each day"),
    clg_setpoint: float = Query(..., description="Cooling setpoint °F"),
    htg_setpoint: float | None = Query(default=None),
    ambient_temp: float = Query(..., description="Ambient temperature °F (constant across range)"),
    start_date: _Date = Query(..., description="First day of range (UTC, YYYY-MM-DD)"),
    end_date: _Date = Query(..., description="Last day of range (UTC, YYYY-MM-DD)"),
    interval_minutes: int = Query(15),
) -> dict:
    """Optimize HVAC schedule over a date range. Each day is solved independently."""
    if end_date < start_date:
        raise HTTPException(422, "end_date must be >= start_date")
    num_days = (end_date - start_date).days + 1
    if num_days > 30:
        raise HTTPException(422, f"Range spans {num_days} days; maximum is 30")

    eff_htg = htg_setpoint if htg_setpoint is not None else clg_setpoint - 4.0
    alpha, beta = _load_zone_coefficients(zone_id, interval_minutes)

    try:
        em_name, _     = _resolve_model_name(zone_id, "em",     granularity)
        etotal_name, _ = _resolve_model_name(zone_id, "etotal", granularity)
        em_model       = _load_thermal_model(em_name)
        etotal_model   = _load_thermal_model(etotal_name)
    except MlflowException as e:
        raise HTTPException(404, f"Model not found: {e}") from e

    days: list[dict] = []
    total_opt_cost   = 0.0
    total_naive_cost = 0.0
    all_optimal      = True

    current = start_date
    while current <= end_date:
        day_result = _optimize_single_day(
            zone_id, zone_temp, clg_setpoint, eff_htg, ambient_temp,
            alpha, beta, em_model, etotal_model, current, interval_minutes,
        )
        if day_result["solver_status"] != "Optimal":
            all_optimal = False
        total_opt_cost   += day_result["total_optimized_cost_usd"]
        total_naive_cost += day_result["total_naive_cost_usd"]
        days.append({"date": current.isoformat(), **day_result})
        current += timedelta(days=1)

    savings_pct = (
        (total_naive_cost - total_opt_cost) / total_naive_cost * 100
        if total_naive_cost > 0 else 0.0
    )

    return {
        "zone_id":                  zone_id,
        "start_date":               start_date.isoformat(),
        "end_date":                 end_date.isoformat(),
        "solver_status":            "Optimal" if all_optimal else "Partial",
        "total_optimized_cost_usd": round(total_opt_cost, 4),
        "total_naive_cost_usd":     round(total_naive_cost, 4),
        "savings_pct":              round(savings_pct, 2),
        "interval_minutes":         interval_minutes,
        "days":                     days,
    }


@router.get("/{zone_id}/optimize")
def optimize_schedule(
    zone_id: str,
    granularity: str = Query("local"),
    zone_temp: float = Query(...),
    clg_setpoint: float = Query(...),
    htg_setpoint: float | None = Query(default=None),
    ambient_temp: float = Query(...),
    planning_date: _Date | None = Query(default=None, alias="date"),
    interval_minutes: int = Query(15),
) -> dict:
    """Optimize HVAC schedule for a single day."""
    target_date = planning_date or datetime.now(timezone.utc).date()
    eff_htg = htg_setpoint if htg_setpoint is not None else clg_setpoint - 4.0
    alpha, beta = _load_zone_coefficients(zone_id, interval_minutes)

    try:
        em_name, _     = _resolve_model_name(zone_id, "em",     granularity)
        etotal_name, _ = _resolve_model_name(zone_id, "etotal", granularity)
        em_model       = _load_thermal_model(em_name)
        etotal_model   = _load_thermal_model(etotal_name)
    except MlflowException as e:
        raise HTTPException(404, f"Model not found: {e}") from e

    day_result = _optimize_single_day(
        zone_id, zone_temp, clg_setpoint, eff_htg, ambient_temp,
        alpha, beta, em_model, etotal_model, target_date, interval_minutes,
    )
    return {"zone_id": zone_id, **day_result}
