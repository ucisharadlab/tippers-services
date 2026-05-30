import { useState, type FormEvent } from "react";
import { ModelVersionSelector } from "./ModelVersionSelector";

export interface OccupancyFormValues {
  spaceId: number;
  start: Date;
  end: Date;
}

interface Props {
  spaceId: number;
  onSubmit: (values: OccupancyFormValues) => void;
  isLoading: boolean;
}

function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function OccupancyForm({ spaceId, onSubmit, isLoading }: Props) {
  const [start, setStart] = useState<string>(toLocalInput(new Date(2024, 3, 1)));
  const [end, setEnd] = useState<string>(toLocalInput(new Date(2024, 8, 30)));
  const [modelSidebarOpen, setModelSidebarOpen] = useState(false);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onSubmit({ spaceId, start: new Date(start), end: new Date(end) });
  }

  return (
    <>
      <form
        onSubmit={handleSubmit}
        className="flex flex-wrap items-end gap-4 rounded-md border border-blue-100 bg-white p-4 shadow-sm"
      >
        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-700">Start</span>
          <input
            type="datetime-local"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className="rounded border border-blue-200 px-3 py-2"
            required
          />
        </label>
        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-700">End</span>
          <input
            type="datetime-local"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            className="rounded border border-blue-200 px-3 py-2"
            required
          />
        </label>
        <button
          type="submit"
          disabled={isLoading}
          className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          {isLoading ? "Loading..." : "Load"}
        </button>
        <button
          type="button"
          onClick={() => setModelSidebarOpen(true)}
          className="rounded border border-blue-200 bg-white px-4 py-2 text-sm font-medium text-blue-700 hover:bg-blue-50"
        >
          Model
        </button>
      </form>

      <ModelVersionSelector
        key={spaceId}
        spaceId={spaceId}
        isOpen={modelSidebarOpen}
        onClose={() => setModelSidebarOpen(false)}
      />
    </>
  );
}
