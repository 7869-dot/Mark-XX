import { useState } from "react";
import { api } from "@/lib/api";
import type { FeedItem } from "@/types";
import { TimeAgo } from "@/components/ui/TimeAgo";

const ICON: Record<string, string> = {
  task: "▤",
  awaiting_approval: "!",
  interaction: "✺",
  memory: "◆",
};

const KIND_LABEL: Record<string, string> = {
  task: "TASK",
  awaiting_approval: "APPROVAL NEEDED",
  interaction: "AGENT INTERACTION",
  memory: "MEMORY",
};

export function FeedItemCard({
  item,
  onAction,
}: {
  item: FeedItem;
  onAction?: () => void;
}) {
  const [working, setWorking] = useState(false);
  const isApproval = item.kind === "awaiting_approval";
  const isInteraction = item.kind === "interaction";

  const approve = async () => {
    setWorking(true);
    try {
      await api.approveTask(item.ref_id);
      onAction?.();
    } finally {
      setWorking(false);
    }
  };
  const reject = async () => {
    setWorking(true);
    try {
      await api.rejectTask(item.ref_id);
      onAction?.();
    } finally {
      setWorking(false);
    }
  };
  const followup = async () => {
    setWorking(true);
    try {
      await api.humanFollowup(item.ref_id);
      onAction?.();
    } finally {
      setWorking(false);
    }
  };

  return (
    <div
      className={`panel p-4 animate-slide-in ${
        isApproval ? "border-amber-axo/40 shadow-amber" : ""
      }`}
    >
      <div className="flex items-start gap-3">
        <div
          className={`w-8 h-8 rounded-md flex items-center justify-center text-lg ${
            isApproval
              ? "bg-amber-axo/10 text-amber-axo"
              : isInteraction
              ? "bg-cyan-axo/10 text-cyan-axo"
              : "bg-ink-700/60 text-silver-axo"
          }`}
        >
          {ICON[item.kind] || "·"}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="label-mono">{KIND_LABEL[item.kind]}</span>
            <span className="text-silver-axo/40">·</span>
            <span className="font-mono text-xs text-silver-axo/70">
              <TimeAgo iso={item.timestamp} />
            </span>
            {typeof item.compatibility_score === "number" && (
              <span className="chip border-cyan-axo/40 text-cyan-axo ml-auto">
                {Math.round(item.compatibility_score)} fit
              </span>
            )}
          </div>
          <div className="font-display text-white text-sm leading-snug mb-1">
            {item.title}
          </div>
          <p className="font-mono text-xs text-silver-axo leading-relaxed">
            {item.description}
          </p>

          {isApproval && (
            <div className="mt-3 flex gap-2">
              <button
                disabled={working}
                onClick={approve}
                className="btn-primary text-xs py-1.5"
              >
                Approve
              </button>
              <button
                disabled={working}
                onClick={reject}
                className="btn-danger text-xs py-1.5"
              >
                Reject
              </button>
              <a
                href={`/tasks?id=${item.ref_id}`}
                className="btn-ghost text-xs py-1.5"
              >
                Review
              </a>
            </div>
          )}

          {isInteraction && !item.outbound && (
            <div className="mt-3 flex gap-2">
              <button
                disabled={working}
                onClick={followup}
                className="btn-primary text-xs py-1.5"
              >
                Connect with human
              </button>
              <a
                href={`/network?agent=${item.other_agent_id}`}
                className="btn-ghost text-xs py-1.5"
              >
                See profile
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
