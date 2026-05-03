import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchModelVersions, setProductionVersion } from "../api/models";

interface Props {
  spaceId: number;
}

export function ModelVersionSelector({ spaceId }: Props) {
  const queryClient = useQueryClient();
  const [selectedVersion, setSelectedVersion] = useState<string>("");

  const { data: versions = [] } = useQuery({
    queryKey: ["modelVersions", spaceId],
    queryFn: () => fetchModelVersions(spaceId),
    staleTime: 30_000,
  });

  const { mutate, isPending, isSuccess, isError } = useMutation({
    mutationFn: (version: string) => setProductionVersion(spaceId, version),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["modelVersions", spaceId] });
      setSelectedVersion("");
    },
  });

  if (versions.length === 0) return null;

  const currentProduction = versions.find((v) => v.is_production)?.version;
  const effectiveSelected = selectedVersion || currentProduction || versions[0].version;

  return (
    <div className="flex flex-col text-sm">
      <span className="mb-1 font-medium text-slate-700">Model Version</span>
      <div className="flex gap-2">
        <select
          value={effectiveSelected}
          onChange={(e) => setSelectedVersion(e.target.value)}
          className="rounded border border-slate-300 px-2 py-2 text-sm"
        >
          {versions.map((v) => (
            <option key={v.version} value={v.version}>
              v{v.version}{v.is_production ? " (production)" : ""}
            </option>
          ))}
        </select>
        <button
          type="button"
          disabled={isPending || effectiveSelected === currentProduction}
          onClick={() => mutate(effectiveSelected)}
          className="rounded bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {isPending ? "Setting..." : "Set as Production"}
        </button>
      </div>
      {isSuccess && (
        <p className="mt-1 text-xs text-green-600">Production alias updated.</p>
      )}
      {isError && (
        <p className="mt-1 text-xs text-red-600">Failed to update alias.</p>
      )}
    </div>
  );
}
