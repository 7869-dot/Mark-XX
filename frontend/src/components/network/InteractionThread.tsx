import { useState } from "react";
import type { Interaction } from "@/types";
import { AgentAvatar } from "@/components/agent/AgentAvatar";
import { TimeAgo } from "@/components/ui/TimeAgo";
import { api } from "@/lib/api";

const STATUS_TONE: Record<string, string> = {
  pending: "border-amber-axo/50 text-amber-axo",
  sent: "border-silver-axo/40 text-silver-axo",
  responded: "border-cyan-axo/40 text-cyan-axo",
  accepted: "border-cyan-axo/50 text-cyan-axo",
  declined: "border-rose-axo/40 text-rose-axo",
};

export function InteractionThread({
  interaction,
  onChange,
}: {
  interaction: Interaction;
  onChange?: () => void;
}) {
  const [working, setWorking] = useState(false);
  const other = interaction.other_agent;
  const pendingHuman =
    !interaction.outbound &&
    (interaction.status === "responded" || interaction.status === "pending");

  const act = async (fn: () => Promise<unknown>) => {
    setWorking(true);
    try {
      await fn();
      onChange?.();
    } finally {
      setWorking(false);
    }
  };

  return (
    <div
      className={`panel p-4 ${
        pendingHuman ? "border-l-2 border-l-amber-axo" : ""
      }`}
    >
      <div className="flex items-center gap-2 mb-3">
        <span className={`chip ${STATUS_TONE[interaction.status] || "border-ink-600 text-silver-axo"}`}>
          {interaction.status}
        </span>
        <span className="chip border-cyan-axo/40 text-cyan-axo">
          {Math.round(interaction.compatibility_score)} fit
        </span>
        <span className="font-mono text-[10px] text-silver-axo/60 ml-auto">
          <TimeAgo iso={interaction.created_at} />
        </span>
      </div>

      <div className="grid md:grid-cols-2 gap-3">
        {/* Initiator side */}
        <div className="panel-inset p-3">
          <div className="flex items-center gap-2 mb-2">
            <AgentAvatar
              seed={interaction.outbound ? "me" : other?.avatar_seed || "x"}
              size={28}
            />
            <span className="font-display text-white text-xs">
              {interaction.outbound ? "Your agent" : other?.name}
            </span>
          </div>
          <p className="font-mono text-xs text-silver-axo leading-relaxed whitespace-pre-wrap">
            {interaction.initiator_message}
          </p>
        </div>
        {/* Target side */}
        <div className="panel-inset p-3">
          <div className="flex items-center gap-2 mb-2">
            <AgentAvatar
              seed={interaction.outbound ? other?.avatar_seed || "x" : "me"}
              size={28}
            />
            <span className="font-display text-white text-xs">
              {interaction.outbound ? other?.name : "Your agent"}
            </span>
          </div>
          <p className="font-mono text-xs text-silver-axo leading-relaxed whitespace-pre-wrap">
            {interaction.target_response || "…awaiting response"}
          </p>
        </div>
      </div>

      <div className="mt-3 panel-inset border-cyan-axo/20 p-3">
        <span className="label-mono">WHAT THIS MEANS</span>
        <p className="font-mono text-xs text-white mt-1 leading-relaxed">
          {interaction.human_summary}
        </p>
      </div>

      {pendingHuman && (
        <div className="mt-3 flex gap-2">
          <button
            disabled={working}
            onClick={() => act(() => api.acceptInteraction(interaction.id))}
            className="btn-primary text-xs py-1.5"
          >
            Follow Up as Human
          </button>
          <button
            disabled={working}
            onClick={() => act(() => api.declineInteraction(interaction.id))}
            className="btn-ghost text-xs py-1.5"
          >
            Ignore
          </button>
        </div>
      )}
    </div>
  );
}
