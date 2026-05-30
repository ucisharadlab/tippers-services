import { useMemo } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { format } from "date-fns";
import type { OptimizerInterval, OptimizerRangeResult } from "../types/api";

interface Props {
  data: OptimizerRangeResult;
  clgSetpoint: number;
}

const STATE_COLORS: Record<OptimizerInterval["state"], string> = {
  cooling:     "#ef4444",
  maintaining: "#f59e0b",
  off:         "#94a3b8",
};

// Shared chart margins — all panels use the same left/right so axes align vertically.
const MARGIN = { top: 4, right: 24, bottom: 0, left: 16 };
const MARGIN_BOTTOM = { top: 4, right: 24, bottom: 4, left: 16 };

function findWindows(
  data: { t: number; value: number }[],
  predicate: (v: number) => boolean,
  stepMs: number,
): { x1: number; x2: number }[] {
  const windows: { x1: number; x2: number }[] = [];
  let start: number | null = null;
  for (const d of data) {
    if (predicate(d.value) && start === null) start = d.t;
    else if (!predicate(d.value) && start !== null) {
      windows.push({ x1: start, x2: d.t });
      start = null;
    }
  }
  if (start !== null && data.length > 0) {
    windows.push({ x1: start, x2: data[data.length - 1].t + stepMs });
  }
  return windows;
}

export function OptimizerChart({ data, clgSetpoint }: Props) {
  const isSingleDay = data.days.length === 1;

  // ── single-day interval data ──────────────────────────────────────────────
  const intervalData = useMemo(() => {
    if (!isSingleDay) return [];
    return data.days[0].intervals.map((iv) => ({
      t:                 new Date(iv.timestamp).getTime(),
      temperature:       iv.temperature,
      naive_temperature: iv.naive_temperature,
      stateValue:        1,
      state:             iv.state,
      tou_price:         iv.tou_price,
      occupancy:         iv.occupancy,
    }));
  }, [isSingleDay, data.days]);

  const stepMs = intervalData.length > 1 ? intervalData[1].t - intervalData[0].t : 0;

  const peakWindows = useMemo(
    () => findWindows(intervalData.map((d) => ({ t: d.t, value: d.tou_price })), (v) => v >= 0.5, stepMs),
    [intervalData, stepMs],
  );

  const occupiedWindows = useMemo(
    () => findWindows(intervalData.map((d) => ({ t: d.t, value: d.occupancy })), (v) => v > 0.05, stepMs),
    [intervalData, stepMs],
  );

  // ── multi-day per-day chart data ──────────────────────────────────────────
  const dayChartData = useMemo(
    () =>
      data.days.map((d) => ({
        date:      format(new Date(d.date + "T12:00:00"), "MMM d"),
        optimized: d.total_optimized_cost_usd,
        naive:     d.total_naive_cost_usd,
      })),
    [data.days],
  );

  // ── shared x-axis tick formatter ──────────────────────────────────────────
  const xAxisTimeProps = {
    dataKey:       "t",
    type:          "number"  as const,
    domain:        ["dataMin", "dataMax"] as [string, string],
    scale:         "time"    as const,
    tickFormatter: (t: number) => format(new Date(t), "HH:mm"),
    minTickGap:    40,
    stroke:        "#64748b",
    fontSize:      11,
  };

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="rounded-md border border-slate-200 bg-white p-4 shadow-sm space-y-4">

      {/* Summary cards — always shown */}
      <div className="flex gap-4 flex-wrap">
        <div className="flex-1 min-w-[140px] rounded-md border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs text-slate-500">Optimized Cost</p>
          <p className="mt-1 text-lg font-semibold text-slate-900">
            ${data.total_optimized_cost_usd.toFixed(2)}
          </p>
        </div>
        <div className="flex-1 min-w-[140px] rounded-md border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs text-slate-500">Naive Baseline</p>
          <p className="mt-1 text-lg font-semibold text-slate-900">
            ${data.total_naive_cost_usd.toFixed(2)}
          </p>
        </div>
        <div className="flex-1 min-w-[140px] rounded-md border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs text-slate-500">Savings</p>
          <p className="mt-1 text-lg font-semibold text-green-600">
            {data.savings_pct.toFixed(1)}%
          </p>
          <span
            className={`text-xs font-medium px-1.5 py-0.5 rounded ${
              data.solver_status === "Optimal"
                ? "bg-green-100 text-green-700"
                : "bg-amber-100 text-amber-700"
            }`}
          >
            {data.solver_status}
          </span>
        </div>
      </div>

      {/* ── MULTI-DAY: per-day cost comparison ──────────────────────────────── */}
      {!isSingleDay && (
        <div>
          <p className="mb-1 text-sm font-medium text-slate-700">
            Daily Cost — Optimized vs Naive ($)
          </p>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={dayChartData}
                margin={{ top: 4, right: 16, bottom: 4, left: 16 }}
                barCategoryGap="20%"
              >
                <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
                <XAxis dataKey="date" stroke="#64748b" fontSize={11} />
                <YAxis
                  stroke="#64748b"
                  fontSize={11}
                  tickFormatter={(v: number) => `$${v.toFixed(2)}`}
                />
                <Tooltip
                  formatter={(v: number, name: string) => [
                    `$${v.toFixed(4)}`,
                    name === "optimized" ? "Optimized" : "Naive",
                  ]}
                />
                <Legend
                  formatter={(v) => (v === "optimized" ? "Optimized" : "Naive Baseline")}
                />
                <Bar dataKey="optimized" name="optimized" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                <Bar dataKey="naive"     name="naive"     fill="#94a3b8" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ── SINGLE-DAY: three-panel chart ───────────────────────────────────── */}
      {isSingleDay && intervalData.length > 0 && (
        <div className="space-y-0">
          <p className="text-sm font-semibold text-slate-800 text-center mb-2">
            24-Hour Plan — {data.zone_id} &mdash; {data.days[0].date}
          </p>

          {/* Panel 1: Temperature */}
          <div>
            <p className="mb-1 text-xs font-medium text-slate-500 ml-1">Zone Temperature (°F)</p>
            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={intervalData} syncId="opt-day" margin={MARGIN}>
                  {/* Background: occupied hours (light blue) */}
                  {occupiedWindows.map((w, i) => (
                    <ReferenceArea
                      key={`occ-${i}`}
                      x1={w.x1} x2={w.x2}
                      fill="#dbeafe" fillOpacity={0.35}
                      strokeOpacity={0}
                    />
                  ))}
                  {/* Background: peak pricing (light pink, on top of occupied) */}
                  {peakWindows.map((w, i) => (
                    <ReferenceArea
                      key={`peak-${i}`}
                      x1={w.x1} x2={w.x2}
                      fill="#fce7f3" fillOpacity={0.55}
                      strokeOpacity={0}
                    />
                  ))}
                  <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
                  <XAxis {...xAxisTimeProps} tick={false} />
                  <YAxis stroke="#64748b" fontSize={11} domain={["auto", "auto"]} width={40} />
                  <Tooltip
                    labelFormatter={(t) => format(new Date(t as number), "HH:mm")}
                    formatter={(v: number, name: string) => [
                      `${v.toFixed(2)} °F`,
                      name === "temperature" ? "Optimized" : "Naive",
                    ]}
                  />
                  <Legend
                    formatter={(v) => {
                      if (v === "temperature") return "Optimized temperature";
                      if (v === "naive_temperature") return "Naive baseline temperature";
                      return v;
                    }}
                    wrapperStyle={{ fontSize: 11 }}
                  />
                  <ReferenceLine
                    y={clgSetpoint}
                    stroke="#94a3b8"
                    strokeDasharray="4 3"
                    label={{ value: `Setpoint ${clgSetpoint}°F`, position: "insideTopRight", fontSize: 10, fill: "#94a3b8" }}
                  />
                  <ReferenceLine
                    y={clgSetpoint + 2}
                    stroke="#ef4444"
                    strokeDasharray="4 3"
                    label={{ value: `Max comfort ${clgSetpoint + 2}°F`, position: "insideTopRight", fontSize: 10, fill: "#ef4444" }}
                  />
                  <Line
                    type="monotone"
                    dataKey="temperature"
                    name="temperature"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="naive_temperature"
                    name="naive_temperature"
                    stroke="#94a3b8"
                    strokeWidth={2}
                    strokeDasharray="6 3"
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Panel 2: HVAC state */}
          <div>
            <p className="mb-0.5 text-xs font-medium text-slate-500 ml-1">HVAC State</p>
            <div className="h-16 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={intervalData}
                  syncId="opt-day"
                  barCategoryGap={0}
                  margin={MARGIN}
                >
                  <XAxis {...xAxisTimeProps} tick={false} />
                  <YAxis hide domain={[0, 1]} />
                  <Tooltip
                    labelFormatter={(t) => format(new Date(t as number), "HH:mm")}
                    formatter={(_v, _n, props) => [
                      (props.payload as { state: string }).state,
                      "State",
                    ]}
                  />
                  <Bar dataKey="stateValue" isAnimationActive={false} maxBarSize={20}>
                    {intervalData.map((entry, i) => (
                      <Cell
                        key={i}
                        fill={STATE_COLORS[entry.state as OptimizerInterval["state"]]}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="flex gap-4 text-xs text-slate-500 mt-1 ml-1">
              {(["cooling", "maintaining", "off"] as const).map((s) => (
                <span key={s} className="flex items-center gap-1">
                  <span
                    className="inline-block h-3 w-3 rounded-sm"
                    style={{ backgroundColor: STATE_COLORS[s] }}
                  />
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </span>
              ))}
            </div>
          </div>

          {/* Panel 3: TOU price */}
          <div className="mt-2">
            <p className="mb-0.5 text-xs font-medium text-slate-500 ml-1">Price ($/kWh)</p>
            <div className="h-24 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={intervalData} syncId="opt-day" margin={MARGIN_BOTTOM}>
                  {peakWindows.map((w, i) => (
                    <ReferenceArea
                      key={`pprice-${i}`}
                      x1={w.x1} x2={w.x2}
                      fill="#fce7f3" fillOpacity={0.55}
                      strokeOpacity={0}
                    />
                  ))}
                  <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
                  <XAxis
                    {...xAxisTimeProps}
                    label={{ value: "Time of Day (UTC)", position: "insideBottomRight", offset: -8, fontSize: 10, fill: "#64748b" }}
                  />
                  <YAxis
                    stroke="#64748b"
                    fontSize={11}
                    domain={[0, 0.6]}
                    ticks={[0.18, 0.5]}
                    tickFormatter={(v: number) => `$${v.toFixed(2)}`}
                    width={40}
                  />
                  <Tooltip
                    labelFormatter={(t) => format(new Date(t as number), "HH:mm")}
                    formatter={(v: number) => [`$${v.toFixed(2)}/kWh`, "TOU Price"]}
                  />
                  <Area
                    type="stepAfter"
                    dataKey="tou_price"
                    stroke="#7c3aed"
                    strokeWidth={1.5}
                    fill="#ede9fe"
                    fillOpacity={0.6}
                    dot={false}
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Background legend */}
          <div className="flex gap-5 text-xs text-slate-500 mt-2 ml-1">
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-5 rounded-sm bg-blue-100" />
              Occupied hours
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-5 rounded-sm bg-pink-100" />
              Peak pricing (22:00–04:00 UTC)
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
