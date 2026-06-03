import { useState } from "react";

interface Props {
  value: string;
  onChange: (value: string) => void;
  zones: string[] | undefined;
  inputClassName?: string;
}

export function VavSelector({ value, onChange, zones, inputClassName }: Props) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const filtered = (zones ?? []).filter((z) =>
    z.toLowerCase().includes(query.toLowerCase())
  );

  function select(z: string) {
    onChange(z);
    setQuery("");
    setOpen(false);
  }

  return (
    <div className="relative">
      <input
        type="text"
        value={open ? query : value}
        placeholder={value ? value : "Search VAV…"}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
        onFocus={() => { setQuery(""); setOpen(true); }}
        onBlur={() => setTimeout(() => { setOpen(false); setQuery(""); }, 150)}
        className={inputClassName}
        required
        autoComplete="off"
      />
      {open && (
        <ul className="absolute z-20 mt-1 max-h-52 w-full overflow-y-auto rounded border border-blue-200 bg-white shadow-lg">
          {filtered.length === 0 ? (
            <li className="px-3 py-2 text-xs italic text-slate-400">No results</li>
          ) : (
            filtered.map((z) => (
              <li
                key={z}
                onMouseDown={() => select(z)}
                className={`cursor-pointer px-3 py-1.5 text-sm ${
                  z === value
                    ? "bg-blue-50 font-medium text-blue-700"
                    : "text-slate-700 hover:bg-blue-50"
                }`}
              >
                {z}
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
