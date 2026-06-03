import { useState, type FormEvent } from "react";
import type { ThermalBaseParams } from "../api/thermal";
import { FieldLabel } from "./FieldLabel";

interface Props {
  zoneId: string;
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

export function ThermalForm({ zoneId, onSubmit, isLoading }: Props) {
  const { start: defaultStart, end: defaultEnd } = defaultRange();

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
      <h3 className="mb-4 text-sm font-semibold text-slate-700">
        Thermal Energy Parameters
        {zoneId && <span className="ml-2 font-normal text-blue-600">— {zoneId}</span>}
      </h3>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(11rem,1fr))] items-end gap-4">
        <label className="flex flex-col text-sm">
          <FieldLabel label="Granularity" tip="Model scope: 'local' uses only this zone's data, 'global' uses building-wide data, 'intermediate' blends both." />
          <select
            value={granularity}
            onChange={(e) =>
              setGranularity(e.target.value as "local" | "global" | "intermediate")
            }
            className="w-full rounded border border-blue-200 px-3 py-2"
          >
            <option value="local">local</option>
            <option value="global">global</option>
            <option value="intermediate">intermediate</option>
          </select>
        </label>

        <label className="flex flex-col text-sm">
          <FieldLabel label="Zone Temp (°F)" tip="Current measured temperature inside the zone at the start of the window." />
          <input
            type="number"
            value={zoneTemp}
            onChange={(e) => setZoneTemp(e.target.value)}
            className="w-full rounded border border-blue-200 px-3 py-2"
            required
          />
        </label>

        <label className="flex flex-col text-sm">
          <FieldLabel label="Clg Setpoint (°F)" tip="Cooling setpoint — the target temperature above which the cooling system activates." />
          <input
            type="number"
            value={clgSetpoint}
            onChange={(e) => setClgSetpoint(e.target.value)}
            className="w-full rounded border border-blue-200 px-3 py-2"
            required
          />
        </label>

        <label className="flex flex-col text-sm">
          <FieldLabel label="Htg Setpoint (°F)" tip="Heating setpoint — the target temperature below which heating activates. Leave blank to omit heating from the model." />
          <input
            type="number"
            value={htgSetpoint}
            onChange={(e) => setHtgSetpoint(e.target.value)}
            placeholder="optional"
            className="w-full rounded border border-blue-200 px-3 py-2"
          />
        </label>

        <label className="flex flex-col text-sm">
          <FieldLabel label="Ambient Temp (°F)" tip="Outdoor air temperature, used to compute heat transfer through the building envelope." />
          <input
            type="number"
            value={ambientTemp}
            onChange={(e) => setAmbientTemp(e.target.value)}
            className="w-full rounded border border-blue-200 px-3 py-2"
            required
          />
        </label>

        <label className="flex flex-col text-sm">
          <FieldLabel label="Interval (min)" tip="Time resolution of the energy calculation. Smaller values give finer granularity but increase computation time." />
          <input
            type="number"
            value={intervalMinutes}
            onChange={(e) => setIntervalMinutes(e.target.value)}
            min={1}
            className="w-full rounded border border-blue-200 px-3 py-2"
            required
          />
        </label>

        <label className="flex flex-col text-sm">
          <FieldLabel label="Start" tip="Start of the time window to model." />
          <input
            type="datetime-local"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className="w-full rounded border border-blue-200 px-3 py-2"
            required
          />
        </label>

        <label className="flex flex-col text-sm">
          <FieldLabel label="End" tip="End of the time window to model." />
          <input
            type="datetime-local"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            className="w-full rounded border border-blue-200 px-3 py-2"
            required
          />
        </label>

        <button
          type="submit"
          disabled={isLoading || !zoneId}
          className="self-end rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          {isLoading ? "Loading..." : "Load"}
        </button>
      </div>
    </form>
  );
}
