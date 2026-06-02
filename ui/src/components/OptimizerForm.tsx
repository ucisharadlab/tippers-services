import { useState, type FormEvent } from "react";
import type { OptimizerParams } from "../api/optimizer";
import { FieldLabel } from "./FieldLabel";
import { useZones } from "../hooks/useZones";

interface Props {
  onSubmit: (params: OptimizerParams) => void;
  isLoading: boolean;
}

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

export function OptimizerForm({ onSubmit, isLoading }: Props) {
  const { data: zones } = useZones();
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
          <FieldLabel label="Zone ID" tip="The VAV box to optimize. Only zones with a deployed model are listed." />
          <select
            value={zoneId}
            onChange={(e) => setZoneId(e.target.value)}
            className="w-44 rounded border border-slate-300 px-3 py-2"
            required
          >
            <option value="" disabled>Select a zone…</option>
            {zones?.map((z) => (
              <option key={z} value={z}>{z}</option>
            ))}
          </select>
        </label>

        <label className="flex flex-col text-sm">
          <FieldLabel label="Granularity" tip="Model scope: 'local' uses only this zone's data, 'global' uses building-wide data, 'intermediate' blends both." />
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
          <FieldLabel label="Initial Temp (°F)" tip="Starting temperature inside the zone at the beginning of the optimization window." />
          <input
            type="number"
            value={zoneTemp}
            onChange={(e) => setZoneTemp(e.target.value)}
            className="w-28 rounded border border-slate-300 px-3 py-2"
            required
          />
        </label>

        <label className="flex flex-col text-sm">
          <FieldLabel label="Clg Setpoint (°F)" tip="Cooling setpoint — the optimizer targets keeping the zone at or below this temperature." />
          <input
            type="number"
            value={clgSetpoint}
            onChange={(e) => setClgSetpoint(e.target.value)}
            className="w-28 rounded border border-slate-300 px-3 py-2"
            required
          />
        </label>

        <label className="flex flex-col text-sm">
          <FieldLabel label="Ambient Temp (°F)" tip="Outdoor air temperature, used to model heat gain from outside the building." />
          <input
            type="number"
            value={ambientTemp}
            onChange={(e) => setAmbientTemp(e.target.value)}
            className="w-28 rounded border border-slate-300 px-3 py-2"
            required
          />
        </label>

        <label className="flex flex-col text-sm">
          <FieldLabel label="Start Date" tip="First day of the optimization window." />
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="rounded border border-slate-300 px-3 py-2"
            required
          />
        </label>

        <label className="flex flex-col text-sm">
          <FieldLabel label="End Date" tip="Last day of the optimization window. Must be on or after the start date." />
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
