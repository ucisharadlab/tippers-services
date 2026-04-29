import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchChildSpaces } from "../api/spaces";

const ROOT_SPACE_ID = 1;

interface NodeProps {
  id: number;
  depth: number;
  selectedId: number;
  onSelect: (id: number) => void;
}

function SpaceTreeNode({ id, depth, selectedId, onSelect }: NodeProps) {
  const [open, setOpen] = useState(false);

  const { data: children, isFetching } = useQuery({
    queryKey: ["spaceChildren", id],
    queryFn: () => fetchChildSpaces(id),
    enabled: open,
    staleTime: 5 * 60_000,
  });

  const isSelected = id === selectedId;

  return (
    <div>
      <div
        style={{ paddingLeft: `${depth * 16 + 4}px` }}
        className={`flex items-center gap-1 rounded py-1 pr-2 cursor-pointer text-sm select-none ${
          isSelected
            ? "bg-slate-900 text-white"
            : "hover:bg-slate-100 text-slate-700"
        }`}
        onClick={() => onSelect(id)}
      >
        <button
          type="button"
          className={`w-4 text-xs shrink-0 ${isSelected ? "text-white" : "text-slate-400 hover:text-slate-700"}`}
          onClick={(e) => {
            e.stopPropagation();
            setOpen((o) => !o);
          }}
        >
          {open ? "▼" : "▶"}
        </button>
        <span>{id}</span>
        {isFetching && <span className="ml-1 text-xs opacity-50">…</span>}
      </div>
      {open && children?.map((childId) => (
        <SpaceTreeNode
          key={childId}
          id={childId}
          depth={depth + 1}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      ))}
      {open && children?.length === 0 && (
        <p
          style={{ paddingLeft: `${(depth + 1) * 16 + 4}px` }}
          className="py-0.5 text-xs text-slate-400 italic"
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
  return (
    <div className="w-48 max-h-64 overflow-y-auto rounded border border-slate-300 bg-white py-1">
      <SpaceTreeNode
        id={ROOT_SPACE_ID}
        depth={0}
        selectedId={selectedId}
        onSelect={onSelect}
      />
    </div>
  );
}
