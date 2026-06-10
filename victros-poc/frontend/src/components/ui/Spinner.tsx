export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div
      role="status"
      aria-label={label}
      className="flex flex-col items-center justify-center gap-3 py-12 text-slate-400"
    >
      <span className="size-8 rounded-full border-2 border-slate-600 border-t-violet-400 animate-spin" />
      <span className="text-sm">{label}</span>
    </div>
  )
}
