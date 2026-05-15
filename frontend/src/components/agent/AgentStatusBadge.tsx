import { PulsingDot } from "@/components/ui/PulsingDot";

const LABELS: Record<string, string> = {
  active: "ACTIVE",
  idle: "IDLE",
  busy: "WORKING",
  sleeping: "ASLEEP",
};

export function AgentStatusBadge({ status }: { status: string }) {
  return (
    <span className="inline-flex items-center gap-2 px-2 py-1 rounded-md bg-ink-900/60 border border-ink-600/60">
      <PulsingDot status={status} />
      <span className="label-mono text-white/90">{LABELS[status] || status}</span>
    </span>
  );
}
