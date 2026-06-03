import { useMemo } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { format } from "date-fns";
import type { OccupancyResponse } from "../types/api";

interface Props {
  data: OccupancyResponse;
}

interface Point {
  t: number;
  history?: number;
  forecast?: number;
}

export function OccupancyChart({ data }: Props) {
  const { points, lastObservedMs } = useMemo(() => {
    const map = new Map<number, Point>();
    for (const h of data.history) {
      const t = new Date(h.starttime).getTime();
      map.set(t, { ...(map.get(t) ?? { t }), history: h.occupancy });
    }
    for (const f of data.forecast) {
      const t = new Date(f.starttime).getTime();
      map.set(t, { ...(map.get(t) ?? { t }), forecast: f.predicted_occupancy });
    }
    const points = Array.from(map.values()).sort((a, b) => a.t - b.t);
    return {
      points,
      lastObservedMs: new Date(data.last_observed).getTime(),
    };
  }, [data]);

  return (
    <div className="rounded-md border border-blue-100 bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-xl font-semibold text-slate-700">
        Occupancy — history vs. forecast
      </h2>
      <div className="h-[30rem] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
            <XAxis
              dataKey="t"
              type="number"
              domain={["dataMin", "dataMax"]}
              scale="time"
              tickFormatter={(t) => format(new Date(t), "MMM d, ha")}
              minTickGap={40}
              stroke="#64748b"
              fontSize={16}
            />
            <YAxis stroke="#64748b" fontSize={16} allowDecimals={false} domain={[0, 16]} />
            <Tooltip
              labelFormatter={(t) => format(new Date(t as number), "MMM d, yyyy h:mm a")}
              formatter={(value: number, name) => [
                value.toFixed(2),
                name === "history" ? "History" : "Forecast",
              ]}
            />
            <Legend />
            <ReferenceLine
              x={lastObservedMs}
              stroke="#94a3b8"
              strokeDasharray="4 4"
              label={{ value: "now", position: "top", fontSize: 14, fill: "#64748b" }}
            />
            <Line
              type="monotone"
              dataKey="history"
              name="History"
              stroke="#0f172a"
              strokeWidth={2}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="forecast"
              name="Forecast"
              stroke="#3b82f6"
              strokeWidth={2}
              strokeDasharray="6 4"
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
