import { useQueries } from "@tanstack/react-query";
import { fetchThermalRange, type ThermalBaseParams } from "../api/thermal";

const MODEL_TYPES = ["em", "etotal", "ec"] as const;

export function useAllThermalRanges(baseParams: ThermalBaseParams | null) {
  const results = useQueries({
    queries: MODEL_TYPES.map((modelType) => ({
      queryKey: [
        "thermalRange",
        modelType,
        baseParams?.zoneId,
        baseParams?.granularity,
        baseParams?.zoneTemp,
        baseParams?.clgSetpoint,
        baseParams?.htgSetpoint,
        baseParams?.ambientTemp,
        baseParams?.start?.toISOString(),
        baseParams?.end?.toISOString(),
        baseParams?.intervalMinutes,
      ],
      queryFn: () => fetchThermalRange({ ...baseParams!, modelType }),
      enabled: baseParams !== null,
      staleTime: 60_000,
      retry: 1,
    })),
  });

  const [emResult, etotalResult, ecResult] = results;
  return {
    em: emResult,
    etotal: etotalResult,
    ec: ecResult,
    isLoading: results.some((r) => r.isLoading),
    isFetching: results.some((r) => r.isFetching),
    error: results.find((r) => r.error)?.error ?? null,
  };
}
