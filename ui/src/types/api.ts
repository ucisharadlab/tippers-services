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
