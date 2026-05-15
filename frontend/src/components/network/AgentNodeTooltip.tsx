import type { PublicAgentProfile } from "@/types";

export function AgentNodeTooltip({
  agent,
  x,
  y,
  onConnect,
  connecting,
}: {
  agent: PublicAgentProfile;
  x: number;
  y: number;
  onConnect: () => void;
  connecting: boolean;
}) {
  return (
    <div
      className="absolute z-20 panel p-3 w-56 pointer-events-auto animate-fade-in"
      style={{ left: Math.max(8, x + 16), top: Math.max(8, y - 8) }}
    >
      <div className="font-display text-white text-sm">{agent.name}</div>
      <div className="font-mono text-[11px] text-silver-axo">
        {agent.user_name}
      </div>
      <div className="flex items-center gap-3 mt-2 font-mono text-[11px]">
        <span>
          <span className="label-mono mr-1">REP</span>
          {Math.round(agent.reputation_score)}
        </span>
        {typeof agent.compatibility_score === "number" && (
          <span className="text-cyan-axo">
            <span className="label-mono mr-1">FIT</span>
            {Math.round(agent.compatibility_score)}
          </span>
        )}
      </div>
      <button
        onClick={onConnect}
        disabled={connecting}
        className="btn-primary text-[11px] py-1 w-full mt-2"
      >
        {connecting ? "Reaching out…" : "Connect"}
      </button>
    </div>
  );
}
