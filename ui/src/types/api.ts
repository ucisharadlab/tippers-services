export interface OccupancyRow {
  spaceid: number;
  starttime: string;
  endtime: string;
  occupancy: number;
}

export interface ForecastInterval {
  starttime: string;
  endtime: string;
  predicted_occupancy: number;
}

export interface OccupancyResponse {
  space_id: number;
  start: string;
  end: string;
  last_observed: string;
  history: OccupancyRow[];
  forecast: ForecastInterval[];
  model_version: string | null;
  forecast_error: string | null;
}

export interface PopularTimesResponse {
  space_id: number;
  // days[0]=Monday … days[6]=Sunday; each has 24 hourly averages (null = no data)
  days: (number | null)[][];
}

export interface ThermalPrediction {
  timestamp: string;
  occupancy_used: number;
  occupancy_fallback?: boolean;
  predicted_energy_kwh_per_min: number;
  etotal_raw?: number;
  em_raw?: number;
}

export interface OptimizerInterval {
  timestamp: string;
  state: "cooling" | "maintaining" | "off";
  temperature: number;
  naive_temperature: number;
  energy_kwh: number;
  interval_cost_usd: number;
  tou_price: number;
  occupancy: number;
}

export interface OptimizerResult {
  zone_id: string;
  solver_status: string;
  total_optimized_cost_usd: number;
  total_naive_cost_usd: number;
  savings_pct: number;
  interval_minutes: number;
  intervals: OptimizerInterval[];
}

export interface OptimizerDayResult {
  date: string;
  solver_status: string;
  total_optimized_cost_usd: number;
  total_naive_cost_usd: number;
  savings_pct: number;
  interval_minutes: number;
  intervals: OptimizerInterval[];
}

export interface OptimizerRangeResult {
  zone_id: string;
  start_date: string;
  end_date: string;
  solver_status: string;
  total_optimized_cost_usd: number;
  total_naive_cost_usd: number;
  savings_pct: number;
  interval_minutes: number;
  days: OptimizerDayResult[];
}
