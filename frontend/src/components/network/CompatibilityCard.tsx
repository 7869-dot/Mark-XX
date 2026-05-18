import type { Discovery } from "@/types";
import { AgentAvatar } from "@/components/agent/AgentAvatar";

function scoreColor(s: number) {
  if (s > 70) return "#00f5d4";
  if (s >= 50) return "#ffb347";
  return "#ff6b6b";
}

function ScoreArc({ score }: { score: number }) {
  const r = 26;
  const c = 2 * Math.PI * r;
  const dash = (Math.min(100, Math.max(0, score)) / 100) * c;
  const color = scoreColor(score);
  return (
    <div className="relative" style={{ width: 64, height: 64 }}>
      <svg width={64} height={64}>
        <circle cx={32} cy={32} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={5} />
        <circle
          cx={32}
          cy={32}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={5}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c - dash}`}
          transform="rotate(-90 32 32)"
          style={{ filter: `drop-shadow(0 0 6px ${color})` }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center font-display text-white text-sm tabular-nums">
        {Math.round(score)}
      </div>
    </div>
  );
}

function Bar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="flex justify-between label-mono mb-1">
        <span>{label}</span>
        <span className="text-silver-axo/80">{Math.round(value)}</span>
      </div>
      <div className="h-1.5 rounded-full bg-ink-700/70 overflow-hidden">
        <div
          className="h-full rounded-full bg-cyan-axo/70"
          style={{ width: `${Math.min(100, value)}%` }}
        />
      </div>
    </div>
  );
}

export function CompatibilityCard({
  discovery,
  onConnect,
  onViewProfile,
  connecting,
}: {
  discovery: Discovery;
  onConnect: () => void;
  onViewProfile: () => void;
  connecting?: boolean;
}) {
  const { agent, breakdown, shared_goals, reason, compatibility_score } = discovery;
  return (
    <div className="panel p-4 flex flex-col gap-4 hover:border-cyan-axo/40 transition">
      <div className="flex items-start gap-3">
        <AgentAvatar seed={agent.avatar_seed || agent.id} size={48} />
        <div className="flex-1 min-w-0">
          <div className="font-display text-white text-base truncate">{agent.name}</div>
          <div className="font-mono text-xs text-silver-axo/80 truncate">
            {agent.user_name}
          </div>
        </div>
        <ScoreArc score={compatibility_score} />
      </div>

      <div className="grid grid-cols-1 gap-2">
        <Bar label="Personality match" value={breakdown.personality} />
        <Bar label="Goal alignment" value={breakdown.goal_alignment} />
        <Bar label="Shared interests" value={breakdown.tag_overlap} />
      </div>

      {shared_goals.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {shared_goals.slice(0, 5).map((g) => (
            <span key={g} className="chip border-cyan-axo/40 text-cyan-axo">
              {g}
            </span>
          ))}
        </div>
      )}

      <p className="font-mono text-xs text-silver-axo italic leading-relaxed">
        {reason}
      </p>

      <div className="flex gap-2">
        <button
          onClick={onConnect}
          disabled={connecting}
          className="btn-primary text-xs py-1.5 flex-1"
        >
          {connecting ? "Connecting…" : "Connect Agents"}
        </button>
        <button onClick={onViewProfile} className="btn-ghost text-xs py-1.5">
          View Profile
        </button>
      </div>
    </div>
  );
}
