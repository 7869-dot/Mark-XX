import { Sparkles } from "lucide-react";
import type { ReactNode } from "react";

type Variant = "info" | "warning" | "success";

const TONE: Record<Variant, string> = {
  info: "border-cyan-axo/30 text-cyan-axo",
  warning: "border-amber-axo/40 text-amber-axo bg-amber-axo/5",
  success: "border-cyan-axo/40 text-cyan-axo bg-cyan-axo/5",
};

export function AgentBanner({
  text,
  actionLabel,
  onAction,
  variant = "info",
  icon,
}: {
  text: ReactNode;
  actionLabel?: string;
  onAction?: () => void;
  variant?: Variant;
  icon?: ReactNode;
}) {
  return (
    <div
      className={`panel px-4 py-3 flex items-center gap-3 ${TONE[variant]}`}
    >
      <span className="shrink-0">
        {icon ?? <Sparkles size={16} />}
      </span>
      <p className="flex-1 font-mono text-xs text-silver-axo leading-relaxed">
        {text}
      </p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="btn-ghost text-xs py-1 px-3 shrink-0"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
