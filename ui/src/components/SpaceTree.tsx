import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchChildSpaces, fetchSpaceNames } from "../api/spaces";

const ROOT_SPACE_ID = 1;

interface NodeProps {
  id: number;
  depth: number;
  selectedId: number;
  onSelect: (id: number) => void;
  names: Record<number, string>;
  defaultOpen?: boolean;
}

function SpaceTreeNode({ id, depth, selectedId, onSelect, names, defaultOpen = false }: NodeProps) {
  const [open, setOpen] = useState(defaultOpen);

  const { data: children, isFetching } = useQuery({
    queryKey: ["spaceChildren", id],
    queryFn: () => fetchChildSpaces(id),
    enabled: open,
    staleTime: 5 * 60_000,
  });

  const isSelected = id === selectedId;
  const label = `${names[id] ?? id} (${id})`;

  return (
    <div>
      <div
        style={{ paddingLeft: `${depth * 16 + 4}px` }}
        className={`flex items-center gap-1 rounded py-1 pr-2 cursor-pointer text-base select-none ${
          isSelected
            ? "bg-blue-600 text-white"
            : "hover:bg-blue-50 text-slate-700"
        }`}
        onClick={() => onSelect(id)}
      >
        <button
          type="button"
          className={`w-4 text-sm shrink-0 ${isSelected ? "text-white" : "text-blue-300 hover:text-blue-600"}`}
          onClick={(e) => {
            e.stopPropagation();
            setOpen((o) => !o);
          }}
        >
          {open ? "▼" : "▶"}
        </button>
        <span>{label}</span>
        {isFetching && <span className="ml-1 text-sm opacity-50">…</span>}
      </div>
      {open && children?.map((childId) => (
        <SpaceTreeNode
          key={childId}
          id={childId}
          depth={depth + 1}
          selectedId={selectedId}
          onSelect={onSelect}
          names={names}
        />
      ))}
      {open && children?.length === 0 && (
        <p
          style={{ paddingLeft: `${(depth + 1) * 16 + 4}px` }}
          className="py-0.5 text-sm text-slate-400 italic"
        >
          No children
        </p>
      )}
    </div>
  );
}

interface Props {
  selectedId: number;
  onSelect: (id: number) => void;
}

export function SpaceTree({ selectedId, onSelect }: Props) {
  const [query, setQuery] = useState("");

  const { data: names = {} } = useQuery({
    queryKey: ["spaceNames"],
    queryFn: fetchSpaceNames,
    staleTime: 10 * 60_000,
  });

  const trimmed = query.trim().toLowerCase();
  const searchResults = trimmed
    ? Object.entries(names)
        .filter(([id, name]) =>
          name.toLowerCase().includes(trimmed) || id.includes(trimmed)
        )
        .map(([id, name]) => ({ id: Number(id), name }))
        .slice(0, 50)
    : null;

  return (
    <div className="rounded border border-blue-200 bg-white">
      <div className="border-b border-blue-100 px-2 py-1.5">
        <input
          type="text"
          placeholder="Search name or ID…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full rounded border border-blue-100 px-2 py-1 text-sm outline-none focus:border-blue-400"
        />
      </div>
      <div className="max-h-60 overflow-y-auto py-1">
        {searchResults ? (
          searchResults.length === 0 ? (
            <p className="px-3 py-2 text-sm text-slate-400 italic">No results</p>
          ) : (
            searchResults.map(({ id }) => (
              <SpaceTreeNode
                key={id}
                id={id}
                depth={0}
                selectedId={selectedId}
                onSelect={(id) => { onSelect(id); setQuery(""); }}
                names={names}
                defaultOpen={true}
              />
            ))
          )
        ) : (
          <SpaceTreeNode
            id={ROOT_SPACE_ID}
            depth={0}
            selectedId={selectedId}
            onSelect={onSelect}
            names={names}
          />
        )}
      </div>
    </div>
  );
}
