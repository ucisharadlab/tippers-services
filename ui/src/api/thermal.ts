import type { ThermalPrediction } from "../types/api";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

export async function fetchZones(): Promise<string[]> {
  const res = await fetch(`${BASE}/services/thermal/zones`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export interface ThermalRangeParams {
  zoneId: string;
  modelType: "em" | "etotal" | "ec";
  granularity: "local" | "global" | "intermediate";
  zoneTemp: number;
  clgSetpoint: number;
  htgSetpoint?: number;
  ambientTemp: number;
  start: Date;
  end: Date;
  intervalMinutes: number;
}

export type ThermalBaseParams = Omit<ThermalRangeParams, "modelType">;

export async function fetchThermalRange(
  params: ThermalRangeParams,
): Promise<ThermalPrediction[]> {
  const p = new URLSearchParams({
    model_type: params.modelType,
    granularity: params.granularity,
    zone_temp: String(params.zoneTemp),
    clg_setpoint: String(params.clgSetpoint),
    ambient_temp: String(params.ambientTemp),
    start: params.start.toISOString(),
    end: params.end.toISOString(),
    interval_minutes: String(params.intervalMinutes),
  });
  if (params.htgSetpoint !== undefined) {
    p.set("htg_setpoint", String(params.htgSetpoint));
  }
  const res = await fetch(
    `${BASE}/services/thermal/${encodeURIComponent(params.zoneId)}/predict/range?${p}`,
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? `API ${res.status}`);
  }
  return res.json();
}
