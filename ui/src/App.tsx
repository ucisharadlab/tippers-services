import { useState } from "react";
import { OccupancyForm, type OccupancyFormValues } from "./components/OccupancyForm";
import { FetchDataForm } from "./components/FetchDataForm";
import { OccupancyChart } from "./components/OccupancyChart";
import { MetadataStrip } from "./components/MetadataStrip";
import { ErrorModal } from "./components/ErrorModal";
import { PopularTimesChart } from "./components/PopularTimesChart";
import { SpaceTree } from "./components/SpaceTree";
import { VavList } from "./components/VavList";
import { ThermalForm } from "./components/ThermalForm";
import { ThermalChart } from "./components/ThermalChart";
import { OptimizerForm } from "./components/OptimizerForm";
import { OptimizerChart } from "./components/OptimizerChart";
import { useOccupancy } from "./hooks/useOccupancy";
import { useAllThermalRanges } from "./hooks/useThermal";
import { useOptimizer } from "./hooks/useOptimizer";
import type { ThermalBaseParams } from "./api/thermal";
import type { OptimizerParams } from "./api/optimizer";

function paramsKey(p: OccupancyFormValues) {
  return `${p.spaceId}-${p.start.toISOString()}-${p.end.toISOString()}`;
}

type Tab = "occupancy" | "thermal" | "optimizer";

export default function App() {
  const [spaceId, setSpaceId] = useState(1);
  const [zoneId, setZoneId] = useState("");
  const [tab, setTab] = useState<Tab>("occupancy");

  // Occupancy
  const [params, setParams] = useState<OccupancyFormValues | null>(null);
  const [dismissedKey, setDismissedKey] = useState<string | null>(null);
  const { data, isLoading, isFetching, error } = useOccupancy(
    params?.spaceId ?? null,
    params?.start ?? new Date(2024, 3, 1),
    params?.end ?? new Date(2024, 8, 30),
  );

  // Thermal
  const [thermalParams, setThermalParams] = useState<ThermalBaseParams | null>(null);
  const {
    em: thermalEm,
    etotal: thermalEtotal,
    ec: thermalEc,
    isLoading: thermalLoading,
    isFetching: thermalFetching,
    error: thermalError,
  } = useAllThermalRanges(thermalParams);

  // Optimizer
  const [optimizerParams, setOptimizerParams] = useState<OptimizerParams | null>(null);
  const {
    data: optimizerData,
    isLoading: optimizerLoading,
    isFetching: optimizerFetching,
    error: optimizerError,
  } = useOptimizer(optimizerParams);

  const forecastError = data?.forecast_error ?? null;
  const showModal = !!forecastError && params !== null && dismissedKey !== paramsKey(params);

  const tabClass = (t: Tab) =>
    `rounded-md px-5 py-2 text-sm font-medium transition-colors ${
      tab === t
        ? "bg-blue-600 text-white shadow-sm"
        : "border border-blue-100 bg-white text-slate-600 hover:bg-blue-50"
    }`;

  return (
    <div className="flex min-h-screen">
      {/* Left sidebar — occupancy tab only */}
      {tab === "occupancy" && <aside className="flex w-72 shrink-0 flex-col border-r border-blue-100 bg-white">
        <div className="border-b border-blue-100 px-4 py-4">
          <h1 className="text-xl font-semibold text-blue-900">DataWhisk</h1>
          <p className="text-sm text-slate-500">Occupancy &amp; forecast viewer</p>
        </div>

        <div className="flex-1 overflow-y-auto p-3">
          <p className="mb-2 text-sm font-medium uppercase tracking-wide text-slate-500">Space</p>
          <SpaceTree selectedId={spaceId} onSelect={setSpaceId} />
          <p className="mt-2 text-sm text-slate-500">
            <span className="text-sm text-slate-500">Selected: </span><span className="text-sm font-medium text-blue-700">Space {spaceId}</span>
          </p>
        </div>

        <div className="border-t border-blue-100 p-3">
          <FetchDataForm />
        </div>
      </aside>}

      {/* Left sidebar — thermal & optimizer tabs */}
      {(tab === "thermal" || tab === "optimizer") && (
        <aside className="flex w-72 shrink-0 flex-col border-r border-blue-100 bg-white">
          <div className="border-b border-blue-100 px-4 py-4">
            <h1 className="text-xl font-semibold text-blue-900">DataWhisk</h1>
            <p className="text-sm text-slate-500">Thermal &amp; optimizer</p>
          </div>

          <div className="flex-1 overflow-y-auto p-3">
            <p className="mb-2 text-sm font-medium uppercase tracking-wide text-slate-500">VAV Zone</p>
            <VavList selectedId={zoneId} onSelect={setZoneId} />
            {zoneId && (
              <p className="mt-2 text-sm text-slate-500">
                <span className="text-sm text-slate-500">Selected: </span><span className="text-sm font-medium text-blue-700">{zoneId}</span>
              </p>
            )}
          </div>
        </aside>
      )}

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-blue-50">
        <div className="mx-auto max-w-7xl px-6 py-8">

          {/* Tab bar */}
          <div className="mb-6 flex justify-center gap-2">
            <button onClick={() => setTab("occupancy")} className={tabClass("occupancy")}>
              Occupancy
            </button>
            <button onClick={() => setTab("thermal")} className={tabClass("thermal")}>
              Thermal
            </button>
            <button onClick={() => setTab("optimizer")} className={tabClass("optimizer")}>
              Optimizer
            </button>
          </div>

          {/* Global overlay */}
          {showModal && (
            <ErrorModal
              message={forecastError!}
              spaceId={params!.spaceId}
              onClose={() => setDismissedKey(paramsKey(params!))}
            />
          )}

          {/* ── Occupancy tab ── */}
          {tab === "occupancy" && (
            <>
              <div className="mb-6">
                <OccupancyForm
                  spaceId={spaceId}
                  onSubmit={setParams}
                  isLoading={isLoading || isFetching}
                />
              </div>

              {error && (
                <div className="mb-6 rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-800">
                  {(error as Error).message}
                </div>
              )}

              {data && (
                <div className="space-y-6">
                  <MetadataStrip data={data} />
                  <OccupancyChart data={data} />
                  <PopularTimesChart spaceId={data.space_id} />
                </div>
              )}

              {!data && !error && !isLoading && (
                <div className="rounded-md border border-blue-100 bg-white p-6 text-base text-slate-400 shadow-sm">
                  Select a space and date range, then click Load.
                </div>
              )}
            </>
          )}

          {/* ── Thermal tab ── */}
          {tab === "thermal" && (
            <>
              <div className="mb-6">
                <ThermalForm
                  zoneId={zoneId}
                  onSubmit={setThermalParams}
                  isLoading={thermalLoading || thermalFetching}
                />
              </div>

              {thermalError && (
                <div className="mb-6 rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-800">
                  {(thermalError as Error).message}
                </div>
              )}

              {(thermalEm.data || thermalEtotal.data || thermalEc.data) && (
                <ThermalChart
                  em={thermalEm.data}
                  etotal={thermalEtotal.data}
                  ec={thermalEc.data}
                />
              )}

              {!thermalEm.data && !thermalEtotal.data && !thermalEc.data && !thermalError && !thermalLoading && (
                <div className="rounded-md border border-blue-100 bg-white p-6 text-sm text-slate-400 shadow-sm">
                  Select a VAV zone from the sidebar, fill in the parameters, then click Load.
                </div>
              )}
            </>
          )}

          {/* ── Optimizer tab ── */}
          {tab === "optimizer" && (
            <>
              <div className="mb-6">
                <OptimizerForm
                  zoneId={zoneId}
                  onSubmit={setOptimizerParams}
                  isLoading={optimizerLoading || optimizerFetching}
                />
              </div>

              {optimizerError && (
                <div className="mb-6 rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-800">
                  {(optimizerError as Error).message}
                </div>
              )}

              {optimizerData && optimizerParams && (
                <OptimizerChart data={optimizerData} clgSetpoint={optimizerParams.clgSetpoint} />
              )}

              {!optimizerData && !optimizerError && !optimizerLoading && (
                <div className="rounded-md border border-blue-100 bg-white p-6 text-sm text-slate-400 shadow-sm">
                  Select a VAV zone from the sidebar, fill in the parameters, then click Optimize.
                </div>
              )}
            </>
          )}

        </div>
      </main>
    </div>
  );
}
