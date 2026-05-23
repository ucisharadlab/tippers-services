import { useState } from "react";
import { OccupancyForm, type OccupancyFormValues } from "./components/OccupancyForm";
import { FetchDataForm } from "./components/FetchDataForm";
import { OccupancyChart } from "./components/OccupancyChart";
import { MetadataStrip } from "./components/MetadataStrip";
import { ErrorModal } from "./components/ErrorModal";
import { PopularTimesChart } from "./components/PopularTimesChart";
import { ThermalForm } from "./components/ThermalForm";
import { ThermalChart } from "./components/ThermalChart";
import { useOccupancy } from "./hooks/useOccupancy";
import { useAllThermalRanges } from "./hooks/useThermal";
import type { ThermalBaseParams } from "./api/thermal";

function defaultRange(): OccupancyFormValues {
  const end = new Date();
  end.setHours(end.getHours() + 24, 0, 0, 0);
  const start = new Date(end);
  start.setDate(start.getDate() - 8);
  return { spaceId: 1, start, end };
}

function paramsKey(p: OccupancyFormValues) {
  return `${p.spaceId}-${p.start.toISOString()}-${p.end.toISOString()}`;
}

export default function App() {
  const [params, setParams] = useState<OccupancyFormValues>(defaultRange);
  const [dismissedKey, setDismissedKey] = useState<string | null>(null);
  const { data, isLoading, isFetching, error } = useOccupancy(
    params.spaceId,
    params.start,
    params.end,
  );

  const [thermalParams, setThermalParams] = useState<ThermalBaseParams | null>(null);
  const {
    em: thermalEm,
    etotal: thermalEtotal,
    ec: thermalEc,
    isLoading: thermalLoading,
    isFetching: thermalFetching,
    error: thermalError,
  } = useAllThermalRanges(thermalParams);

  const forecastError = data?.forecast_error ?? null;
  const showModal = !!forecastError && dismissedKey !== paramsKey(params);

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900">DataWhisk</h1>
        <p className="text-sm text-slate-600">
          Occupancy history and forecast viewer.
        </p>
      </header>

      <div className="mb-6">
        <OccupancyForm
          initial={params}
          onSubmit={setParams}
          isLoading={isLoading || isFetching}
        />
      </div>

      <div className="mb-6">
        <FetchDataForm />
      </div>

      {error && (
        <div className="mb-6 rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-800">
          {(error as Error).message}
        </div>
      )}

      {showModal && (
        <ErrorModal
          message={forecastError!}
          spaceId={params.spaceId}
          onClose={() => setDismissedKey(paramsKey(params))}
        />
      )}

      {data && (
        <div className="space-y-6">
          <MetadataStrip data={data} />
          <OccupancyChart data={data} />
          <PopularTimesChart spaceId={data.space_id} />
        </div>
      )}

      {!data && !error && !isLoading && (
        <div className="rounded-md border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">
          Select a space and date range, then click Load.
        </div>
      )}

      <section className="mt-10">
        <header className="mb-4">
          <h2 className="text-xl font-semibold text-slate-900">Thermal Energy</h2>
          <p className="text-sm text-slate-600">Predicted HVAC energy usage over a time range.</p>
        </header>

        <div className="mb-6">
          <ThermalForm
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
          <div className="rounded-md border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">
            Fill in the parameters above, then click Load.
          </div>
        )}
      </section>
    </div>
  );
}
