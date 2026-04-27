import { useState } from "react";
import { OccupancyForm, type OccupancyFormValues } from "./components/OccupancyForm";
import { OccupancyChart } from "./components/OccupancyChart";
import { MetadataStrip } from "./components/MetadataStrip";
import { useOccupancy } from "./hooks/useOccupancy";

function defaultRange(): OccupancyFormValues {
  const end = new Date();
  end.setHours(end.getHours() + 24, 0, 0, 0);
  const start = new Date(end);
  start.setDate(start.getDate() - 8);
  return { spaceId: 1, start, end };
}

export default function App() {
  const [params, setParams] = useState<OccupancyFormValues>(defaultRange);
  const { data, isLoading, isFetching, error } = useOccupancy(
    params.spaceId,
    params.start,
    params.end,
  );

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

      {error && (
        <div className="mb-6 rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-800">
          {(error as Error).message}
        </div>
      )}

      {data && (
        <div className="space-y-6">
          <MetadataStrip data={data} />
          <OccupancyChart data={data} />
        </div>
      )}

      {!data && !error && !isLoading && (
        <div className="rounded-md border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">
          Enter a space id and date range, then click Load.
        </div>
      )}
    </div>
  );
}
