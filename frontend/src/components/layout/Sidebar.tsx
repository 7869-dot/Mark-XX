import { NavLink } from "react-router-dom";
import {
  Home,
  Mail,
  Calendar,
  User,
  Network,
  Rss,
  ListChecks,
  Inbox,
  Settings,
  Users,
  Globe,
  Send,
  Radar,
  Handshake,
  Sparkles,
} from "lucide-react";
import { AgentSwitcher } from "@/components/layout/AgentSwitcher";
import { useAuth } from "@/hooks/useAuth";
import { useIntegrations } from "@/hooks/useIntegrations";
import { classNames } from "@/lib/utils";
import type { ReactNode } from "react";

const NAV: { to: string; label: string; icon: ReactNode; badge?: "unread" }[] = [
  { to: "/dashboard", label: "Command Center", icon: <Home size={16} /> },
  { to: "/jarvis", label: "Jarvis", icon: <Sparkles size={16} /> },
  { to: "/gmail", label: "Inbox", icon: <Mail size={16} />, badge: "unread" },
  { to: "/agent-inbox", label: "Agent inbox", icon: <Send size={16} /> },
  { to: "/calendar", label: "Calendar", icon: <Calendar size={16} /> },
  { to: "/agent", label: "Agent", icon: <User size={16} /> },
  { to: "/agents", label: "My agents", icon: <Users size={16} /> },
  { to: "/feed", label: "Feed", icon: <Rss size={16} /> },
  { to: "/world", label: "World", icon: <Radar size={16} /> },
  { to: "/collab", label: "Collaborate", icon: <Handshake size={16} /> },
  { to: "/directory", label: "Directory", icon: <Globe size={16} /> },
  { to: "/network", label: "Network", icon: <Network size={16} /> },
  { to: "/tasks", label: "Tasks", icon: <ListChecks size={16} /> },
  { to: "/inbox", label: "Approvals", icon: <Inbox size={16} /> },
  { to: "/settings/integrations", label: "Settings", icon: <Settings size={16} /> },
];

/** Maps the agent's lifecycle status to one of the three sidebar dot states. */
function statusDot(status: string | undefined) {
  if (status === "thinking" || status === "processing")
    return { color: "var(--accent-gold)", label: "Processing" };
  if (status === "asleep" || status === "offline")
    return { color: "var(--text-tertiary)", label: "Offline" };
  return { color: "var(--accent-green)", label: "Active" };
}

export function Sidebar() {
  const { agent, signOut } = useAuth();
  const { unread } = useIntegrations();
  if (!agent) return null;

  const dot = statusDot(agent.status);

  return (
    <aside
      className="hidden md:flex flex-col w-60 shrink-0"
      style={{
        background: "var(--bg-sidebar)",
        color: "var(--text-on-dark)",
      }}
    >
      <div className="px-5 pt-6 pb-5 flex items-center gap-2">
        <span
          className="text-lg tracking-[0.18em]"
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 400,
            color: "var(--text-on-dark)",
          }}
        >
          Axolot
        </span>
      </div>

      <AgentSwitcher />

      <nav className="flex-1 px-2 flex flex-col gap-0.5 overflow-y-auto">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              classNames(
                "flex items-center gap-3 pr-3 py-2 rounded-r-md text-sm transition relative",
                isActive ? "sidebar-nav-active" : "sidebar-nav-idle"
              )
            }
            style={({ isActive }) =>
              isActive
                ? {
                    fontFamily: "var(--font-body)",
                    background: "var(--bg-elevated)",
                    color: "var(--text-primary)",
                    fontWeight: 500,
                    paddingLeft: 12,
                    borderLeft: "2px solid var(--accent-blue)",
                  }
                : {
                    fontFamily: "var(--font-body)",
                    color: "var(--text-secondary)",
                    paddingLeft: 14, // 12 + 2 to match active inset
                    borderLeft: "2px solid transparent",
                  }
            }
          >
            <span className="leading-none">{item.icon}</span>
            <span className="flex-1">{item.label}</span>
            {item.badge === "unread" && unread > 0 && (
              <span
                className="inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-[10px] font-medium"
                style={{
                  background: "var(--accent-blue)",
                  color: "#FFFFFF",
                  fontFamily: "var(--font-data)",
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
        <span
          className="inline-block w-2 h-2 rounded-full shrink-0"
          style={{ background: dot.color }}
          aria-label={dot.label}
        />
        <div className="min-w-0 flex-1">
          <div
            className="text-sm truncate"
            style={{
              fontFamily: "var(--font-body)",
              fontWeight: 500,
              color: "var(--text-primary)",
            }}
          >
            {agent.name}
          </div>
          <div
            className="text-[11px] truncate"
            style={{
              fontFamily: "var(--font-data)",
              color: "var(--text-secondary)",
            }}
          >
            {dot.label}
          </div>
        </div>
      </div>

      <div className="px-4 pb-4">
        <button
          onClick={signOut}
          className="w-full text-xs px-3 py-1.5 rounded-md transition"
          style={{
            background: "transparent",
            border: "1px solid var(--border-subtle)",
            color: "var(--text-secondary)",
            fontFamily: "var(--font-body)",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--bg-elevated)";
            e.currentTarget.style.color = "var(--text-primary)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
            e.currentTarget.style.color = "var(--text-secondary)";
          }}
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
