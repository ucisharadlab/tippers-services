import { format } from "date-fns";
import type { OccupancyResponse } from "../types/api";

interface Props {
  data: OccupancyResponse;
}

export function MetadataStrip({ data }: Props) {
  const lastObserved = format(new Date(data.last_observed), "MMM d, yyyy h:mm a");
  return (
    <div className="grid grid-cols-2 gap-4 rounded-md border border-blue-100 bg-white p-4 text-sm shadow-sm sm:grid-cols-4">
      <Field label="Space" value={String(data.space_id)} />
      <Field label="Model version" value={data.model_version ?? "—"} />
      <Field label="Last observed" value={lastObserved} />
      <Field
        label="Points"
        value={`${data.history.length} hist · ${data.forecast.length} fc`}
      />
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 font-medium text-blue-900">{value}</div>
    </div>
  );
}
