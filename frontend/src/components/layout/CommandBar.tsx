import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";

export function CommandBar() {
  const { agent } = useAuth();
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    if (!agent) return;
    const tick = async () => {
      try {
        const pending = await api.pendingTasks();
        setPendingCount(pending.length);
      } catch {
        /* ignore */
      }
    };
    tick();
    const id = setInterval(tick, 30000);
    return () => clearInterval(id);
  }, [agent]);

  return (
    <header className="h-14 border-b border-ink-700/60 bg-ink-900/70 backdrop-blur-md flex items-center justify-between px-6">
      <div className="flex items-center gap-3">
        <span className="label-mono">SYSTEM</span>
        <span className="font-mono text-xs text-silver-axo">
          {new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </span>
        <span className="text-silver-axo/50">·</span>
        <span className="font-mono text-xs text-cyan-axo">
          {agent?.status === "busy" ? "executing" : "standing by"}
        </span>
      </div>

      <div className="flex items-center gap-3">
        {pendingCount > 0 && (
          <a
            href="/inbox"
            className="chip border-amber-axo/40 text-amber-axo bg-amber-axo/5 hover:bg-amber-axo/10"
          >
            {pendingCount} need{pendingCount === 1 ? "s" : ""} approval
          </a>
        )}
        <div className="font-mono text-xs text-silver-axo">
          {agent ? agent.user_name : ""}
        </div>
      </div>
    </header>
  );
}
