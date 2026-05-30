import { useState, type FormEvent } from "react";
import type { OptimizerParams } from "../api/optimizer";

interface Props {
  onSubmit: (params: OptimizerParams) => void;
  isLoading: boolean;
}

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

export function OptimizerForm({ onSubmit, isLoading }: Props) {
  const [zoneId, setZoneId]           = useState("");
  const [granularity, setGranularity] = useState<"local" | "global" | "intermediate">("local");
  const [zoneTemp, setZoneTemp]       = useState("76");
  const [clgSetpoint, setClgSetpoint] = useState("72");
  const [ambientTemp, setAmbientTemp] = useState("85");
  const [startDate, setStartDate]     = useState(todayStr());
  const [endDate, setEndDate]         = useState(todayStr());

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onSubmit({
      zoneId,
      granularity,
      zoneTemp:    Number(zoneTemp),
      clgSetpoint: Number(clgSetpoint),
      ambientTemp: Number(ambientTemp),
      startDate,
      endDate,
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-md border border-slate-200 bg-white p-4 shadow-sm"
    >
      <h3 className="mb-4 text-sm font-semibold text-slate-700">Optimizer Parameters</h3>
      <div className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-700">Zone ID</span>
          <input
            type="text"
            value={zoneId}
            onChange={(e) => setZoneId(e.target.value)}
            placeholder="e.g. VAV1.10"
            className="w-36 rounded border border-slate-300 px-3 py-2"
            required
          />
        </label>

        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-700">Granularity</span>
          <select
            value={granularity}
            onChange={(e) => setGranularity(e.target.value as "local" | "global" | "intermediate")}
            className="rounded border border-slate-300 px-3 py-2"
          >
            <option value="local">local</option>
            <option value="global">global</option>
            <option value="intermediate">intermediate</option>
          </select>
        </label>

        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-700">Initial Temp (°F)</span>
          <input
            type="number"
            value={zoneTemp}
            onChange={(e) => setZoneTemp(e.target.value)}
            className="w-28 rounded border border-slate-300 px-3 py-2"
            required
          />
        </label>

        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-700">Clg Setpoint (°F)</span>
          <input
            type="number"
            value={clgSetpoint}
            onChange={(e) => setClgSetpoint(e.target.value)}
            className="w-28 rounded border border-slate-300 px-3 py-2"
            required
          />
        </label>

        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-700">Ambient Temp (°F)</span>
          <input
            type="number"
            value={ambientTemp}
            onChange={(e) => setAmbientTemp(e.target.value)}
            className="w-28 rounded border border-slate-300 px-3 py-2"
            required
          />
        </label>

        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-700">Start Date</span>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="rounded border border-slate-300 px-3 py-2"
            required
          />
        </label>

        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-700">End Date</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            min={startDate}
            className="rounded border border-slate-300 px-3 py-2"
            required
          />
        </label>

        <button
          type="submit"
          disabled={isLoading}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {isLoading ? "Optimizing..." : "Optimize"}
        </button>
      </div>
    </form>
  );
}
