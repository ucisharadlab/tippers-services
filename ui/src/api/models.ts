const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

export interface ModelVersion {
  version: string;
  is_production: boolean;
  created_timestamp: number;
  run_id: string;
  rmse: number | null;
  mae: number | null;
}

export async function fetchModelVersions(spaceId: number): Promise<ModelVersion[]> {
  const res = await fetch(`${BASE}/admin/models/${spaceId}/versions`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function setProductionVersion(spaceId: number, version: string): Promise<void> {
  const res = await fetch(
    `${BASE}/admin/models/${spaceId}/set-production?version=${encodeURIComponent(version)}`,
    { method: "POST" },
  );
  if (!res.ok) throw new Error(`API ${res.status}`);
}
