const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

export async function fetchChildSpaces(spaceId: number): Promise<number[]> {
  const res = await fetch(`${BASE}/services/spaces/${spaceId}/children`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}
