import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchModelVersions, setProductionVersion } from "../api/models";

interface Props {
  spaceId: number;
  isOpen: boolean;
  onClose: () => void;
}

export function ModelVersionSelector({ spaceId, isOpen, onClose }: Props) {
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
      queryClient.invalidateQueries({ queryKey: ["occupancy", spaceId] });
      setSelectedVersion("");
    },
  });

  const currentProduction = versions.find((v) => v.is_production)?.version;
  const effectiveSelected = selectedVersion || currentProduction || versions[0]?.version;

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/20"
          onClick={onClose}
        />
      )}

      <div
        className={`fixed right-0 top-0 z-50 h-full w-80 bg-white shadow-xl transition-transform duration-300 ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <h2 className="text-base font-semibold text-slate-900">Model Versions</h2>
            <button
              type="button"
              onClick={onClose}
              className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            >
              ✕
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-5">
            {versions.length === 0 ? (
              <p className="text-sm text-slate-500">No model versions available for this space.</p>
            ) : (
              <div className="space-y-4">
                {currentProduction && (
                  <div className="rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-600">
                    Current production: <span className="font-semibold">v{currentProduction}</span>
                  </div>
                )}

                <div className="space-y-2">
                  {versions.map((v) => {
                    const isSelected = effectiveSelected === v.version;
                    return (
                      <button
                        key={v.version}
                        type="button"
                        onClick={() => setSelectedVersion(v.version)}
                        className={`w-full rounded-md border px-4 py-3 text-left text-sm transition-colors ${
                          isSelected
                            ? "border-slate-900 bg-slate-900 text-white"
                            : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium">v{v.version}</span>
                          {v.is_production && (
                            <span className={`text-xs font-medium ${isSelected ? "text-slate-300" : "text-green-600"}`}>
                              production
                            </span>
                          )}
                        </div>
                        {(v.rmse != null || v.mae != null) && (
                          <div className={`mt-1 text-xs ${isSelected ? "text-slate-300" : "text-slate-400"}`}>
                            {v.rmse != null && `RMSE: ${v.rmse.toFixed(4)}`}
                            {v.rmse != null && v.mae != null && "  ·  "}
                            {v.mae != null && `MAE: ${v.mae.toFixed(4)}`}
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>

                <button
                  type="button"
                  disabled={isPending || effectiveSelected === currentProduction}
                  onClick={() => effectiveSelected && mutate(effectiveSelected)}
                  className="w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
                >
                  {isPending ? "Setting..." : "Set as Production"}
                </button>

                {isSuccess && (
                  <p className="text-xs text-green-600">Production alias updated.</p>
                )}
                {isError && (
                  <p className="text-xs text-red-600">Failed to update alias.</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
