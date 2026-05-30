import { useState } from "react";

type Status = "idle" | "loading" | "success" | "error";

export function FetchDataForm() {
  const [spaceId, setSpaceId] = useState<string>("");
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState<string>("");

  async function handleFetch() {
    const id = parseInt(spaceId, 10);
    if (!id) return;
    setStatus("loading");
    setMessage("");
    try {
      const res = await fetch(`/api/export/occupancy/${id}`, { method: "POST" });
      if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
      const data = await res.json();
      setMessage(`Saved ${data.row_count} rows → ${data.file}`);
      setStatus("success");
    } catch (e) {
      setMessage((e as Error).message);
      setStatus("error");
    }
  }

  return (
    <div>
      <p className="mb-2 text-xs font-medium text-slate-500 uppercase tracking-wide">Export Data</p>
      <input
        type="number"
        value={spaceId}
        onChange={(e) => { setSpaceId(e.target.value); setStatus("idle"); }}
        placeholder="Space ID (e.g. 473)"
        className="mb-2 w-full rounded border border-blue-200 px-2 py-1.5 text-sm"
      />
      <button
        onClick={handleFetch}
        disabled={!spaceId || status === "loading"}
        className="w-full rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {status === "loading" ? "Fetching…" : "Fetch data"}
      </button>
      {status === "success" && (
        <p className="mt-2 text-xs text-emerald-700 break-all">{message}</p>
      )}
      {status === "error" && (
        <p className="mt-2 text-xs text-red-700">{message}</p>
      )}
    </div>
  );
}
