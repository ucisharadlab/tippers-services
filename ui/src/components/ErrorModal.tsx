interface Props {
  message: string;
  onClose: () => void;
}

export function ErrorModal({ message, onClose }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 shadow-lg">
        <h2 className="mb-2 text-base font-semibold text-slate-900">No model available</h2>
        <p className="mb-5 text-sm text-slate-600">{message}</p>
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
