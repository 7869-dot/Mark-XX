import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, Plus, Star } from "lucide-react";
import { AgentAvatar } from "@/components/agent/AgentAvatar";
import { useActiveAgent } from "@/hooks/useActiveAgent";

/**
 * Persistent agent switcher — shown above the sidebar nav.
 *
 * Selecting an agent writes its id to localStorage (via setActiveAgent);
 * lib/api.ts then stamps X-Agent-Id on every subsequent request so chat
 * + proactive behaviors run in that agent's voice. "Use primary agent"
 * clears the override.
 */
export function AgentSwitcher() {
  const { agents, activeAgent, setActiveAgent, primaryAgent } = useActiveAgent();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, [open]);

  if (!activeAgent) return null;

  const onDarkPanel = {
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.08)",
  };

  return (
    <div className="px-3 pb-3 relative" ref={rootRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-2 py-2 rounded-md transition"
        style={onDarkPanel}
        onMouseEnter={(e) =>
          (e.currentTarget.style.background = "rgba(255,255,255,0.08)")
        }
        onMouseLeave={(e) =>
          (e.currentTarget.style.background = "rgba(255,255,255,0.04)")
        }
      >
        <AgentAvatar
          seed={activeAgent.avatar_seed || activeAgent.id}
          size={28}
        />
        <div className="min-w-0 flex-1 text-left">
          <div
            className="text-xs truncate"
            style={{
              fontFamily: "var(--font-body)",
              fontWeight: 500,
              color: "#FFFFFF",
            }}
          >
            {activeAgent.name}
          </div>
          <div
            className="text-[10px] truncate"
            style={{
              fontFamily: "var(--font-data)",
              color: "var(--text-on-dark-muted)",
            }}
          >
            {activeAgent.is_primary ? "Primary agent" : "Active agent"}
          </div>
        </div>
        <ChevronDown
          size={14}
          style={{
            color: "var(--text-on-dark-muted)",
            transform: open ? "rotate(180deg)" : undefined,
            transition: "transform 120ms",
          }}
        />
      </button>

      {open && (
        <div
          className="absolute left-3 right-3 mt-1 z-20 rounded-md overflow-hidden"
          style={{
            background: "#252528",
            border: "1px solid rgba(255,255,255,0.12)",
            boxShadow: "0 12px 32px rgba(0,0,0,0.45)",
          }}
        >
          <div className="max-h-64 overflow-y-auto">
            {agents.map((a) => {
              const isActive = a.id === activeAgent.id;
              return (
                <button
                  key={a.id}
                  onClick={() => {
                    setActiveAgent(a.is_primary ? null : a.id);
                    setOpen(false);
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 transition text-left"
                  style={{
                    background: isActive ? "rgba(27,79,216,0.18)" : "transparent",
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive)
                      e.currentTarget.style.background =
                        "rgba(255,255,255,0.06)";
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) e.currentTarget.style.background = "transparent";
                  }}
                >
                  <AgentAvatar seed={a.avatar_seed || a.id} size={24} />
                  <div className="min-w-0 flex-1">
                    <div
                      className="text-xs truncate"
                      style={{
                        fontFamily: "var(--font-body)",
                        fontWeight: isActive ? 600 : 400,
                        color: "#FFFFFF",
                      }}
                    >
                      {a.name}
                    </div>
                  </div>
                  {a.is_primary && (
                    <Star
                      size={11}
                      fill="currentColor"
                      style={{ color: "#D4A017" }}
                    />
                  )}
                </button>
              );
            })}
          </div>
          <Link
            to="/agents"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-3 py-2 transition"
            style={{
              borderTop: "1px solid rgba(255,255,255,0.08)",
              color: "var(--text-on-dark-muted)",
            }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.background = "rgba(255,255,255,0.06)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.background = "transparent")
            }
          >
            <Plus size={14} />
            <span className="text-xs">Create new agent</span>
          </Link>
          {primaryAgent && primaryAgent.id !== activeAgent.id && (
            <button
              onClick={() => {
                setActiveAgent(null);
                setOpen(false);
              }}
              className="w-full text-left px-3 py-2 transition"
              style={{
                borderTop: "1px solid rgba(255,255,255,0.08)",
                color: "var(--text-on-dark-muted)",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "rgba(255,255,255,0.06)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "transparent")
              }
            >
              <span className="text-xs">Switch back to primary</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
