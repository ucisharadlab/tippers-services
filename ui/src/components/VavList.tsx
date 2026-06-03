import { useState } from "react";
import { useZones } from "../hooks/useZones";

interface Props {
  selectedId: string;
  onSelect: (id: string) => void;
}

export function VavList({ selectedId, onSelect }: Props) {
  const [query, setQuery] = useState("");
  const { data: zones = [], isLoading } = useZones();

  const filtered = query.trim()
    ? zones.filter((z) => z.toLowerCase().includes(query.toLowerCase()))
    : zones;

  return (
    <div className="rounded border border-blue-200 bg-white">
      <div className="border-b border-blue-100 px-2 py-1.5">
        <input
          type="text"
          placeholder="Search VAV…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full rounded border border-blue-100 px-2 py-1 text-sm outline-none focus:border-blue-400"
        />
      </div>
      <div className="max-h-[60vh] overflow-y-auto py-1">
        {isLoading && (
          <p className="px-3 py-2 text-sm italic text-slate-400">Loading…</p>
        )}
        {!isLoading && filtered.length === 0 && (
          <p className="px-3 py-2 text-sm italic text-slate-400">No results</p>
        )}
        {filtered.map((z) => (
          <div
            key={z}
            onClick={() => onSelect(z)}
            className={`mx-1 cursor-pointer select-none rounded px-3 py-1.5 text-base ${
              z === selectedId
                ? "bg-blue-600 text-white"
                : "text-slate-700 hover:bg-blue-50"
            }`}
          >
            {z}
          </div>
        ))}
      </div>
    </div>
  );
}
