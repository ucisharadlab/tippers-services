import { useMemo } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { format } from "date-fns";
import type { ThermalPrediction } from "../types/api";

interface Props {
  em: ThermalPrediction[] | undefined;
  etotal: ThermalPrediction[] | undefined;
  ec: ThermalPrediction[] | undefined;
}

interface Point {
  t: number;
  em?: number;
  etotal?: number;
  ec?: number;
}

export function ThermalChart({ em, etotal, ec }: Props) {
  const points = useMemo<Point[]>(() => {
    const map = new Map<number, Point>();

    for (const d of em ?? []) {
      const t = new Date(d.timestamp).getTime();
      map.set(t, { ...(map.get(t) ?? { t }), em: d.predicted_energy_kwh_per_min });
    }
    for (const d of etotal ?? []) {
      const t = new Date(d.timestamp).getTime();
      map.set(t, { ...(map.get(t) ?? { t }), etotal: d.predicted_energy_kwh_per_min });
    }
    for (const d of ec ?? []) {
      const t = new Date(d.timestamp).getTime();
      map.set(t, { ...(map.get(t) ?? { t }), ec: d.predicted_energy_kwh_per_min });
    }

    return Array.from(map.values()).sort((a, b) => a.t - b.t);
  }, [em, etotal, ec]);

  return (
    <div className="rounded-md border border-blue-100 bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-sm font-medium text-slate-700">Energy Usage Over Time</h2>
      <div className="h-96 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 8, right: 16, bottom: 8, left: 16 }}>
            <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
            <XAxis
              dataKey="t"
              type="number"
              domain={["dataMin", "dataMax"]}
              scale="time"
              tickFormatter={(t) => format(new Date(t), "MMM d, ha")}
              minTickGap={40}
              stroke="#64748b"
              fontSize={12}
            />
            <YAxis
              stroke="#64748b"
              fontSize={12}
              tickFormatter={(v: number) => v.toFixed(4)}
              label={{
                value: "kWh/min",
                angle: -90,
                position: "insideLeft",
                fontSize: 11,
                fill: "#64748b",
                dx: -8,
              }}
            />
            <Tooltip
              labelFormatter={(t) => format(new Date(t as number), "MMM d, yyyy h:mm a")}
              formatter={(value: number, name: string) => [
                value.toFixed(4),
                name,
              ]}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="em"
              name="Energy to Maintain"
              stroke="#f97316"
              strokeWidth={2}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="etotal"
              name="Total Energy"
              stroke="#0f172a"
              strokeWidth={2}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="ec"
              name="Cooling Energy"
              stroke="#3b82f6"
              strokeWidth={2}
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
