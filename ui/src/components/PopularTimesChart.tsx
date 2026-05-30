import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { fetchPopularTimes } from "../api/occupancy";

const DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"] as const;
const TICK_HOURS = new Set([9, 12, 15, 18, 21]);

function formatHour(hour: number): string {
  if (hour === 0) return "12a";
  if (hour < 12) return `${hour}a`;
  if (hour === 12) return "12p";
  return `${hour - 12}p`;
}

interface TooltipPayload {
  payload: { hour: number; avg: number | null };
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayload[];
}) {
  if (!active || !payload?.length) return null;
  const { hour, avg } = payload[0].payload;
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      <p className="font-medium text-slate-700">{formatHour(hour).toUpperCase()}</p>
      {avg === null ? (
        <p className="text-slate-400">No data</p>
      ) : (
        <p className="text-slate-600">
          Avg {avg} {avg === 1 ? "person" : "people"}
        </p>
      )}
    </div>
  );
}

interface Props {
  spaceId: number;
}

// JS getDay(): 0=Sun…6=Sat → convert to Mon=0…Sun=6
function todayDow(): number {
  return (new Date().getDay() + 6) % 7;
}

export function PopularTimesChart({ spaceId }: Props) {
  const today = todayDow();
  const [selectedDay, setSelectedDay] = useState(today);
  const currentHour = new Date().getHours();

  const { data, isLoading } = useQuery({
    queryKey: ["popularTimes", spaceId],
    queryFn: () => fetchPopularTimes(spaceId),
    staleTime: 30 * 60 * 1000,
  });

  const dayData = data?.days[selectedDay] ?? null;
  const chartData = Array.from({ length: 24 }, (_, hour) => ({
    hour,
    avg: dayData?.[hour] ?? null,
  }));

  const nonNulls = dayData?.filter((v): v is number => v !== null) ?? [];
  const maxVal = nonNulls.length > 0 ? Math.max(...nonNulls) : 1;
  const hasData = nonNulls.length > 0;

  return (
    <div className="rounded-md border border-blue-100 bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-sm font-semibold text-slate-700">Popular Times</h2>

      <div className="mb-4 flex gap-1">
        {DAYS.map((day, idx) => (
          <button
            key={day}
            onClick={() => setSelectedDay(idx)}
            className={`flex-1 rounded py-1 text-xs font-medium transition-colors ${
              idx === selectedDay
                ? "bg-blue-600 text-white"
                : "text-slate-500 hover:bg-blue-50"
            }`}
          >
            {day}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex h-32 items-center justify-center text-xs text-slate-400">
          Loading…
        </div>
      ) : !hasData ? (
        <div className="flex h-32 items-center justify-center text-xs text-slate-400">
          No historical data for this day
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={chartData} barCategoryGap="20%" margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
            <XAxis
              dataKey="hour"
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11, fill: "#94a3b8" }}
              tickFormatter={(h) => (TICK_HOURS.has(h) ? formatHour(h) : "")}
            />
            <YAxis hide domain={[0, maxVal * 1.25]} />
            <Tooltip content={<CustomTooltip />} cursor={false} />
            <Bar dataKey="avg" radius={[3, 3, 0, 0]} maxBarSize={18}>
              {chartData.map(({ hour }) => (
                <Cell
                  key={hour}
                  fill={
                    selectedDay === today && hour === currentHour
                      ? "#3b82f6"
                      : "#cbd5e1"
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
