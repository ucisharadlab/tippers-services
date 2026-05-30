import type { OptimizerRangeResult } from "../types/api";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

export interface OptimizerParams {
  zoneId: string;
  granularity: "local" | "global" | "intermediate";
  zoneTemp: number;
  clgSetpoint: number;
  htgSetpoint?: number;
  ambientTemp: number;
  startDate: string;   // YYYY-MM-DD
  endDate: string;     // YYYY-MM-DD
  intervalMinutes?: number;
}

export async function fetchOptimizedRangeSchedule(
  params: OptimizerParams,
): Promise<OptimizerRangeResult> {
  const p = new URLSearchParams({
    granularity:  params.granularity,
    zone_temp:    String(params.zoneTemp),
    clg_setpoint: String(params.clgSetpoint),
    ambient_temp: String(params.ambientTemp),
    start_date:   params.startDate,
    end_date:     params.endDate,
  });
  if (params.htgSetpoint !== undefined) p.set("htg_setpoint", String(params.htgSetpoint));
  if (params.intervalMinutes !== undefined) p.set("interval_minutes", String(params.intervalMinutes));

  const res = await fetch(
    `${BASE}/services/thermal/${encodeURIComponent(params.zoneId)}/optimize/range?${p}`,
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? `API ${res.status}`);
  }
  return res.json();
}
