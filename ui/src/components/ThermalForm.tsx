import { useState, type FormEvent } from "react";
import type { ThermalBaseParams } from "../api/thermal";

interface Props {
  onSubmit: (params: ThermalBaseParams) => void;
  isLoading: boolean;
}

function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function defaultRange() {
  const end = new Date();
  end.setHours(end.getHours() + 24, 0, 0, 0);
  const start = new Date(end);
  start.setDate(start.getDate() - 1);
  return { start, end };
}

export function ThermalForm({ onSubmit, isLoading }: Props) {
  const { start: defaultStart, end: defaultEnd } = defaultRange();

  const [zoneId, setZoneId] = useState("");
  const [granularity, setGranularity] = useState<"local" | "global" | "intermediate">("local");
  const [zoneTemp, setZoneTemp] = useState("72");
  const [clgSetpoint, setClgSetpoint] = useState("75");
  const [htgSetpoint, setHtgSetpoint] = useState("");
  const [ambientTemp, setAmbientTemp] = useState("85");
  const [intervalMinutes, setIntervalMinutes] = useState("60");
  const [start, setStart] = useState(toLocalInput(defaultStart));
  const [end, setEnd] = useState(toLocalInput(defaultEnd));

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onSubmit({
      zoneId,
      granularity,
      zoneTemp: Number(zoneTemp),
      clgSetpoint: Number(clgSetpoint),
      htgSetpoint: htgSetpoint !== "" ? Number(htgSetpoint) : undefined,
      ambientTemp: Number(ambientTemp),
      start: new Date(start),
      end: new Date(end),
      intervalMinutes: Number(intervalMinutes),
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-md border border-blue-100 bg-white p-4 shadow-sm"
    >
      <h3 className="mb-4 text-sm font-semibold text-slate-700">Thermal Energy Parameters</h3>
      <div className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-700">Zone ID</span>
          <input
            type="text"
            value={zoneId}
            onChange={(e) => setZoneId(e.target.value)}
            placeholder="e.g. VAV-101"
            className="w-36 rounded border border-blue-200 px-3 py-2"
            required
          />
        </label>

        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-700">Granularity</span>
          <select
            value={granularity}
            onChange={(e) =>
              setGranularity(e.target.value as "local" | "global" | "intermediate")
            }
            className="rounded border border-blue-200 px-3 py-2"
          >
            <option value="local">local</option>
            <option value="global">global</option>
            <option value="intermediate">intermediate</option>
          </select>
        </label>

        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-700">Zone Temp (°F)</span>
          <input
            type="number"
            value={zoneTemp}
            onChange={(e) => setZoneTemp(e.target.value)}
            className="w-28 rounded border border-blue-200 px-3 py-2"
            required
          />
        </label>

        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-700">Clg Setpoint (°F)</span>
          <input
            type="number"
            value={clgSetpoint}
            onChange={(e) => setClgSetpoint(e.target.value)}
            className="w-28 rounded border border-blue-200 px-3 py-2"
            required
          />
        </label>

        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-700">Htg Setpoint (°F)</span>
          <input
            type="number"
            value={htgSetpoint}
            onChange={(e) => setHtgSetpoint(e.target.value)}
            placeholder="optional"
            className="w-28 rounded border border-blue-200 px-3 py-2"
          />
        </label>

        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-700">Ambient Temp (°F)</span>
          <input
            type="number"
            value={ambientTemp}
            onChange={(e) => setAmbientTemp(e.target.value)}
            className="w-28 rounded border border-blue-200 px-3 py-2"
            required
          />
        </label>

        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-700">Interval (min)</span>
          <input
            type="number"
            value={intervalMinutes}
            onChange={(e) => setIntervalMinutes(e.target.value)}
            min={1}
            className="w-24 rounded border border-blue-200 px-3 py-2"
            required
          />
        </label>

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
      </div>
    </form>
  );
}
