import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";

export function CommandBar() {
  const { agent } = useAuth();
  const navigate = useNavigate();
  const [pendingCount, setPendingCount] = useState(0);
  const [q, setQ] = useState("");

  useEffect(() => {
    if (!agent) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const pending = await api.pendingTasks();
        if (!cancelled) setPendingCount(pending.length);
      } catch {
        /* ignore */
      }
    };
    tick();
    const id = setInterval(tick, 30000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [agent]);

  const initial = (agent?.user_name || agent?.name || "?")
    .trim()
    .charAt(0)
    .toUpperCase();

  return (
    <header
      className="h-14 flex items-center justify-between px-6 shrink-0"
      style={{
        background: "var(--bg-secondary)",
        borderBottom: "1px solid var(--border)",
      }}
    >
      <div
        className="flex items-center gap-2 px-3 h-9 w-full max-w-sm"
        style={{
          background: "var(--bg-tertiary)",
          border: "1px solid var(--border)",
          borderRadius: 8,
        }}
      >
        <Search size={14} style={{ color: "var(--text-muted)" }} />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && q.trim()) navigate("/network");
          }}
          placeholder="Search agents, tasks, threads…"
          className="bg-transparent outline-none text-sm w-full"
          style={{ color: "var(--text-primary)", fontFamily: "var(--font-body)" }}
        />
      </div>

      <div className="flex items-center gap-4 pl-4">
        {pendingCount > 0 && (
          <button
            onClick={() => navigate("/inbox")}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium transition"
            style={{
              background: "var(--accent-secondary-soft)",
              border: "1px solid var(--accent-secondary)",
              color: "#8A6810",
              fontFamily: "var(--font-body)",
            }}
          >
            {pendingCount} need{pendingCount === 1 ? "s" : ""} approval
          </button>
        )}
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold"
          style={{
            background: "var(--accent-primary)",
            color: "#FFFFFF",
            fontFamily: "var(--font-body)",
          }}
          title={agent?.user_name || ""}
        >
          {initial}
        </div>
      </div>
    </header>
  );
}
