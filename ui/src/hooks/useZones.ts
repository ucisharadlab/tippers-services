import { useQuery } from "@tanstack/react-query";
import { fetchZones } from "../api/thermal";

export function useZones() {
  return useQuery({
    queryKey: ["zones"],
    queryFn: fetchZones,
    staleTime: 5 * 60_000,
  });
}
