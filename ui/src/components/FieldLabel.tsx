interface Props {
  label: string;
  tip: string;
}

export function FieldLabel({ label, tip }: Props) {
  return (
    <span className="group relative mb-1 inline-flex items-center gap-1 font-medium text-slate-700">
      {label}
      <span className="inline-flex h-3.5 w-3.5 cursor-default select-none items-center justify-center rounded-full bg-slate-200 text-[9px] font-bold text-slate-500">
        ?
      </span>
      <span className="pointer-events-none absolute bottom-full left-0 z-10 mb-1.5 w-52 rounded-md bg-slate-800 px-2.5 py-1.5 text-xs font-normal text-white opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100">
        {tip}
      </span>
    </span>
  );
}
