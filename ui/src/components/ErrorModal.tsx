import { useEffect, useRef, useState } from "react";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

interface Props {
  message: string;
  spaceId: number;
  onClose: () => void;
}

type IngestStatus = "idle" | "running" | "done" | "error";

export function ErrorModal({ message, spaceId, onClose }: Props) {
  const [hasData, setHasData] = useState<boolean | null>(null);
  const [rowCount, setRowCount] = useState(0);
  const [ingestStatus, setIngestStatus] = useState<IngestStatus>("idle");
  const [output, setOutput] = useState("");
  const outputRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    setHasData(null);
    setIngestStatus("idle");
    setOutput("");
    fetch(`${BASE}/services/occupancy/${spaceId}/has-data`)
      .then((r) => r.json())
      .then((d) => { setHasData(d.has_data); setRowCount(d.row_count); })
      .catch(() => setHasData(null));
  }, [spaceId]);

  useEffect(() => {
    if (ingestStatus !== "running") return;
    const id = setInterval(async () => {
      const r = await fetch(`${BASE}/ingest/occupancy/${spaceId}/status`);
      const d = await r.json();
      setOutput(d.output ?? "");
      if (d.status !== "running") {
        setIngestStatus(d.status as IngestStatus);
        if (d.status === "done") setHasData(true);
        clearInterval(id);
      }
    }, 5000);
    return () => clearInterval(id);
  }, [ingestStatus, spaceId]);

  // Auto-scroll output to bottom as new lines arrive
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  async function handleIngest() {
    setIngestStatus("running");
    setOutput("");
    await fetch(`${BASE}/ingest/occupancy/${spaceId}`, { method: "POST" });
  }

  const showOutput = ingestStatus === "running" || ingestStatus === "done" || ingestStatus === "error";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-lg rounded-lg border border-slate-200 bg-white p-6 shadow-lg">
        <h2 className="mb-2 text-base font-semibold text-slate-900">No model available</h2>
        <p className="mb-4 text-sm text-slate-600">{message}</p>

        <div className="mb-4 rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
          {hasData === null && <span className="text-slate-400">Checking occupancy data…</span>}
          {hasData === true && ingestStatus === "idle" && (
            <span className="text-green-700">
              Occupancy data found ({rowCount.toLocaleString()} rows).
            </span>
          )}
          {hasData === false && ingestStatus === "idle" && (
            <div className="flex flex-col gap-2">
              <span className="text-amber-700">No occupancy data for this space.</span>
              <button
                onClick={handleIngest}
                className="rounded bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800"
              >
                Input data into occupancy table
              </button>
            </div>
          )}
          {ingestStatus === "running" && (
            <span className="text-slate-500">Ingesting data… this may take several minutes.</span>
          )}
          {ingestStatus === "done" && (
            <span className="text-green-700">Data ingested successfully.</span>
          )}
          {ingestStatus === "error" && (
            <span className="text-red-700">Ingestion failed — see output below.</span>
          )}
        </div>

        {showOutput && (
          <pre
            ref={outputRef}
            className="mb-4 h-48 overflow-y-auto rounded border border-slate-200 bg-slate-900 p-3 text-xs text-green-400 whitespace-pre-wrap"
          >
            {output || "Starting…"}
          </pre>
        )}

        <button
          onClick={onClose}
          className="w-full rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
