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
