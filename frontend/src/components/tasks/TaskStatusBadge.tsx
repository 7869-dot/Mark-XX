const COLORS: Record<string, string> = {
  queued: "border-silver-axo/40 text-silver-axo",
  running: "border-cyan-axo/40 text-cyan-axo bg-cyan-axo/5",
  completed: "border-cyan-axo/30 text-cyan-axo",
  failed: "border-rose-axo/40 text-rose-axo",
  awaiting_human: "border-amber-axo/40 text-amber-axo bg-amber-axo/5",
  rejected: "border-rose-axo/40 text-rose-axo",
};

export function TaskStatusBadge({ status }: { status: string }) {
  return (
    <span className={`chip ${COLORS[status] || COLORS.queued}`}>
      {status.replace("_", " ")}
    </span>
  );
}
