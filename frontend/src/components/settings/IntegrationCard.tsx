import type { ReactNode } from "react";
import { PulsingDot } from "@/components/ui/PulsingDot";

export function IntegrationCard({
  name,
  description,
  icon,
  isConnected,
  onConnect,
  onDisconnect,
  comingSoon = false,
  busy = false,
  lastSynced,
}: {
  name: string;
  description: string;
  icon: ReactNode;
  isConnected?: boolean;
  onConnect?: () => void;
  onDisconnect?: () => void;
  comingSoon?: boolean;
  busy?: boolean;
  lastSynced?: string | null;
}) {
  return (
    <div
      className={`panel p-5 flex items-start gap-4 ${
        comingSoon ? "opacity-50" : ""
      }`}
    >
      <div className="w-10 h-10 rounded-md bg-ink-700/60 border border-ink-600 flex items-center justify-center text-cyan-axo">
        {icon}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h3 className="font-display text-white text-base">{name}</h3>
          {comingSoon && (
            <span className="chip border-ink-600 text-silver-axo">
              Coming soon
            </span>
          )}
          {isConnected && !comingSoon && (
            <span className="inline-flex items-center gap-1.5 chip border-cyan-axo/40 text-cyan-axo">
              <PulsingDot status="active" size={6} />
              Connected
            </span>
          )}
        </div>
        <p className="font-mono text-xs text-silver-axo mt-1 leading-relaxed">
          {description}
        </p>
        {isConnected && lastSynced && (
          <p className="font-mono text-[10px] text-silver-axo/50 mt-2">
            Last synced {lastSynced}
          </p>
        )}
      </div>

      <div className="shrink-0">
        {comingSoon ? (
          <button disabled className="btn-ghost text-xs opacity-60">
            Unavailable
          </button>
        ) : isConnected ? (
          <button
            onClick={onDisconnect}
            disabled={busy}
            className="btn-ghost text-xs"
          >
            Disconnect
          </button>
        ) : (
          <button
            onClick={onConnect}
            disabled={busy}
            className="btn-primary text-xs"
          >
            {busy ? "Connecting…" : "Connect"}
          </button>
        )}
      </div>
    </div>
  );
}
