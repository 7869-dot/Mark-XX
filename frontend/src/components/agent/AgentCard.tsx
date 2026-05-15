import type { PublicAgentProfile } from "@/types";
import { AgentAvatar } from "./AgentAvatar";
import { AgentStatusBadge } from "./AgentStatusBadge";

export function AgentCard({
  agent,
  onClick,
  onInteract,
}: {
  agent: PublicAgentProfile;
  onClick?: () => void;
  onInteract?: () => void;
}) {
  return (
    <div
      className="panel p-4 flex flex-col gap-3 hover:border-cyan-axo/40 transition cursor-pointer"
      onClick={onClick}
    >
      <div className="flex items-start gap-3">
        <AgentAvatar
          seed={agent.avatar_seed || agent.id}
          personality={agent.personality_vector as any}
          size={48}
        />
        <div className="flex-1 min-w-0">
          <div className="font-display text-white text-base truncate">
            {agent.name}
          </div>
          <div className="font-mono text-xs text-silver-axo/80 truncate">
            {agent.user_name}
          </div>
        </div>
        <AgentStatusBadge status={agent.status} />
      </div>

      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-3">
          <span>
            <span className="label-mono mr-1">REP</span>
            <span className="text-white tabular-nums">
              {Math.round(agent.reputation_score)}
            </span>
          </span>
          <span>
            <span className="label-mono mr-1">DONE</span>
            <span className="text-white tabular-nums">
              {agent.total_tasks_completed}
            </span>
          </span>
        </div>
        {typeof agent.compatibility_score === "number" && (
          <span className="chip border-cyan-axo/40 text-cyan-axo">
            {Math.round(agent.compatibility_score)} fit
          </span>
        )}
      </div>

      {agent.interests?.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {agent.interests.slice(0, 4).map((t) => (
            <span key={t} className="chip border-ink-600 text-silver-axo">
              {t}
            </span>
          ))}
        </div>
      )}

      {onInteract && (
        <button
          className="btn-primary text-xs py-1.5"
          onClick={(e) => {
            e.stopPropagation();
            onInteract();
          }}
        >
          Initiate interaction →
        </button>
      )}
    </div>
  );
}
