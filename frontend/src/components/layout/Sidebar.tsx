import { NavLink } from "react-router-dom";
import {
  Home,
  MessageSquare,
  Mail,
  Calendar,
  User,
  Network,
  Compass,
  Rss,
  Store,
  ListChecks,
  Inbox,
  Settings,
} from "lucide-react";
import { AgentOrb, statusToOrbState } from "@/components/agent/AgentOrb";
import { useAuth } from "@/hooks/useAuth";
import { useIntegrations } from "@/hooks/useIntegrations";
import { classNames } from "@/lib/utils";
import type { ReactNode } from "react";

const NAV: { to: string; label: string; icon: ReactNode; badge?: "unread" }[] = [
  { to: "/dashboard", label: "Command Center", icon: <Home size={16} /> },
  { to: "/chat", label: "Chat", icon: <MessageSquare size={16} /> },
  { to: "/gmail", label: "Inbox", icon: <Mail size={16} />, badge: "unread" },
  { to: "/calendar", label: "Calendar", icon: <Calendar size={16} /> },
  { to: "/agent", label: "Agent", icon: <User size={16} /> },
  { to: "/feed", label: "Feed", icon: <Rss size={16} /> },
  { to: "/discover", label: "Discover", icon: <Compass size={16} /> },
  { to: "/marketplace", label: "Marketplace", icon: <Store size={16} /> },
  { to: "/network", label: "Network", icon: <Network size={16} /> },
  { to: "/tasks", label: "Tasks", icon: <ListChecks size={16} /> },
  { to: "/inbox", label: "Approvals", icon: <Inbox size={16} /> },
  { to: "/settings/integrations", label: "Settings", icon: <Settings size={16} /> },
];

export function Sidebar() {
  const { agent, signOut } = useAuth();
  const { unread } = useIntegrations();
  if (!agent) return null;

  const orbState = statusToOrbState(agent.status);

  return (
    <aside
      className="hidden md:flex flex-col w-60 shrink-0"
      style={{
        background: "var(--bg-surface)",
        borderRight: "1px solid var(--border-subtle)",
      }}
    >
      <div className="px-5 pt-6 pb-5 flex items-center gap-2">
        <span
          className="text-lg tracking-[0.25em]"
          style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}
        >
          <span style={{ color: "var(--text-primary)" }}>AXO</span>
          <span style={{ color: "var(--teal-bright)" }}>LOT</span>
        </span>
      </div>

      <nav className="flex-1 px-3 flex flex-col gap-1 overflow-y-auto">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              classNames(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition",
                isActive ? "nav-active" : "nav-idle"
              )
            }
            style={({ isActive }) =>
              isActive
                ? {
                    fontFamily: "var(--font-display)",
                    background: "var(--bg-elevated)",
                    color: "var(--teal-bright)",
                    border: "1px solid var(--border-active)",
                  }
                : {
                    fontFamily: "var(--font-display)",
                    color: "var(--text-secondary)",
                    border: "1px solid transparent",
                  }
            }
          >
            <span className="leading-none">{item.icon}</span>
            <span className="flex-1">{item.label}</span>
            {item.badge === "unread" && unread > 0 && (
              <span
                className="chip"
                style={{
                  borderColor: "var(--border-active)",
                  color: "var(--teal-bright)",
                }}
              >
                {unread > 99 ? "99+" : unread}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      <div
        className="p-4 flex items-center gap-3"
        style={{ borderTop: "1px solid var(--border-subtle)" }}
      >
        <AgentOrb state={orbState} size={36} />
        <div className="min-w-0 flex-1">
          <div
            className="text-sm truncate"
            style={{ fontFamily: "var(--font-display)", color: "var(--text-primary)" }}
          >
            {agent.name}
          </div>
          <div
            className="text-[11px] truncate"
            style={{ fontFamily: "var(--font-data)", color: "var(--text-muted)" }}
          >
            {orbState === "thinking"
              ? "Thinking…"
              : orbState === "alert"
              ? "Asleep"
              : "Online · Ready"}
          </div>
        </div>
      </div>

      <div className="px-4 pb-4">
        <button onClick={signOut} className="btn-ghost w-full text-xs">
          Sign out
        </button>
      </div>
    </aside>
  );
}
