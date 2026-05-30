import { useQuery } from "@tanstack/react-query";
import { fetchOptimizedRangeSchedule, type OptimizerParams } from "../api/optimizer";

export function useOptimizer(params: OptimizerParams | null) {
  return useQuery({
    queryKey: ["optimizer", params],
    queryFn: () => fetchOptimizedRangeSchedule(params!),
    enabled: params !== null,
    staleTime: 60_000,
    retry: 1,
  });
}
