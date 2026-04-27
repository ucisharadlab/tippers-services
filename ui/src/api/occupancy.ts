import type { OccupancyResponse } from "../types/api";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

export async function fetchOccupancy(
  spaceId: number,
  start: Date,
  end: Date,
): Promise<OccupancyResponse> {
  const params = new URLSearchParams({
    start: start.toISOString(),
    end: end.toISOString(),
  });
  const res = await fetch(`${BASE}/services/occupancy/${spaceId}?${params}`);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API ${res.status}: ${detail}`);
  }
  return res.json();
}
