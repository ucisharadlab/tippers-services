import { useQuery } from "@tanstack/react-query";
import { fetchOccupancy, fetchSpaceIds } from "../api/occupancy";

export function useSpaceIds() {
  return useQuery({
    queryKey: ["spaceIds"],
    queryFn: fetchSpaceIds,
    staleTime: 5 * 60_000,
  });
}

export function useOccupancy(
  spaceId: number | null,
  start: Date,
  end: Date,
) {
  return useQuery({
    queryKey: ["occupancy", spaceId, start.toISOString(), end.toISOString()],
    queryFn: () => fetchOccupancy(spaceId as number, start, end),
    enabled: spaceId !== null,
    staleTime: 60_000,
    retry: 1,
  });
}
