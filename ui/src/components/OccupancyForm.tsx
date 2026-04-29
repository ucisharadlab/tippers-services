import { useState, type FormEvent } from "react";

export interface OccupancyFormValues {
  spaceId: number;
  start: Date;
  end: Date;
}

interface Props {
  initial: OccupancyFormValues;
  onSubmit: (values: OccupancyFormValues) => void;
  isLoading: boolean;
  spaceIds: number[];
  isLoadingSpaces: boolean;
}

function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function OccupancyForm({ initial, onSubmit, isLoading, spaceIds, isLoadingSpaces }: Props) {
  const [spaceId, setSpaceId] = useState<string>(String(initial.spaceId));
  const [start, setStart] = useState<string>(toLocalInput(initial.start));
  const [end, setEnd] = useState<string>(toLocalInput(initial.end));

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const id = parseInt(spaceId, 10);
    if (Number.isNaN(id)) return;
    onSubmit({
      spaceId: id,
      start: new Date(start),
      end: new Date(end),
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-wrap items-end gap-4 rounded-md border border-slate-200 bg-white p-4 shadow-sm"
    >
      <label className="flex flex-col text-sm">
        <span className="mb-1 font-medium text-slate-700">Space ID</span>
        <select
          value={spaceId}
          onChange={(e) => setSpaceId(e.target.value)}
          disabled={isLoadingSpaces}
          className="w-36 rounded border border-slate-300 px-3 py-2"
          required
        >
          {isLoadingSpaces && <option value="">Loading…</option>}
          {spaceIds.map((id) => (
            <option key={id} value={id}>{id}</option>
          ))}
        </select>
      </label>
      <label className="flex flex-col text-sm">
        <span className="mb-1 font-medium text-slate-700">Start</span>
        <input
          type="datetime-local"
          value={start}
          onChange={(e) => setStart(e.target.value)}
          className="rounded border border-slate-300 px-3 py-2"
          required
        />
      </label>
      <label className="flex flex-col text-sm">
        <span className="mb-1 font-medium text-slate-700">End</span>
        <input
          type="datetime-local"
          value={end}
          onChange={(e) => setEnd(e.target.value)}
          className="rounded border border-slate-300 px-3 py-2"
          required
        />
      </label>
      <button
        type="submit"
        disabled={isLoading}
        className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
      >
        {isLoading ? "Loading..." : "Load"}
      </button>
    </form>
  );
}
