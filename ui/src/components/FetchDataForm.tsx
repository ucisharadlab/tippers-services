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
    <div className="flex flex-wrap items-end gap-3 rounded-md border border-blue-100 bg-white p-4 shadow-sm">
      <label className="flex flex-col text-sm">
        <span className="mb-1 font-medium text-slate-700">Space ID</span>
        <input
          type="number"
          value={spaceId}
          onChange={(e) => { setSpaceId(e.target.value); setStatus("idle"); }}
          placeholder="e.g. 473"
          className="w-32 rounded border border-blue-200 px-3 py-2"
        />
      </label>
      <button
        onClick={handleFetch}
        disabled={!spaceId || status === "loading"}
        className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {status === "loading" ? "Fetching..." : "Fetch data"}
      </button>
      {status === "success" && (
        <span className="text-sm text-emerald-700">{message}</span>
      )}
      {status === "error" && (
        <span className="text-sm text-red-700">{message}</span>
      )}
    </div>
  );
}
