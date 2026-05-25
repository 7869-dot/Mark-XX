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
  Users,
  Globe,
  Send,
} from "lucide-react";
import { AgentSwitcher } from "@/components/layout/AgentSwitcher";
import { useAuth } from "@/hooks/useAuth";
import { useIntegrations } from "@/hooks/useIntegrations";
import { classNames } from "@/lib/utils";
import type { ReactNode } from "react";

const NAV: { to: string; label: string; icon: ReactNode; badge?: "unread" }[] = [
  { to: "/dashboard", label: "Command Center", icon: <Home size={16} /> },
  { to: "/chat", label: "Chat", icon: <MessageSquare size={16} /> },
  { to: "/gmail", label: "Inbox", icon: <Mail size={16} />, badge: "unread" },
  { to: "/agent-inbox", label: "Agent inbox", icon: <Send size={16} /> },
  { to: "/calendar", label: "Calendar", icon: <Calendar size={16} /> },
  { to: "/agent", label: "Agent", icon: <User size={16} /> },
  { to: "/agents", label: "My agents", icon: <Users size={16} /> },
  { to: "/feed", label: "Feed", icon: <Rss size={16} /> },
  { to: "/directory", label: "Directory", icon: <Globe size={16} /> },
  { to: "/discover", label: "Discover", icon: <Compass size={16} /> },
  { to: "/marketplace", label: "Marketplace", icon: <Store size={16} /> },
  { to: "/network", label: "Network", icon: <Network size={16} /> },
  { to: "/tasks", label: "Tasks", icon: <ListChecks size={16} /> },
  { to: "/inbox", label: "Approvals", icon: <Inbox size={16} /> },
  { to: "/settings/integrations", label: "Settings", icon: <Settings size={16} /> },
];

/** Maps the agent's lifecycle status to one of the three sidebar dot states. */
function statusDot(status: string | undefined) {
  if (status === "thinking" || status === "processing")
    return { color: "#D4A017", label: "Processing" };
  if (status === "asleep" || status === "offline")
    return { color: "#9A9A9A", label: "Offline" };
  return { color: "#1A7F5A", label: "Active" };
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

      <nav className="flex-1 px-3 flex flex-col gap-0.5 overflow-y-auto">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              classNames(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition",
                isActive ? "sidebar-nav-active" : "sidebar-nav-idle"
              )
            }
            style={({ isActive }) =>
              isActive
                ? {
                    fontFamily: "var(--font-body)",
                    background: "var(--bg-sidebar-hover)",
                    color: "#FFFFFF",
                    fontWeight: 500,
                  }
                : {
                    fontFamily: "var(--font-body)",
                    color: "var(--text-on-dark-muted)",
                  }
            }
          >
            <span className="leading-none">{item.icon}</span>
            <span className="flex-1">{item.label}</span>
            {item.badge === "unread" && unread > 0 && (
              <span
                className="inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-[10px] font-medium"
                style={{
                  background: "var(--accent-primary)",
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
        style={{ borderTop: "1px solid rgba(255,255,255,0.08)" }}
      >
        <span
          className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
          style={{ background: dot.color, boxShadow: `0 0 6px ${dot.color}` }}
          aria-label={dot.label}
        />
        <div className="min-w-0 flex-1">
          <div
            className="text-sm truncate"
            style={{
              fontFamily: "var(--font-body)",
              fontWeight: 500,
              color: "#FFFFFF",
            }}
          >
            {agent.name}
          </div>
          <div
            className="text-[11px] truncate"
            style={{
              fontFamily: "var(--font-data)",
              color: "var(--text-on-dark-muted)",
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
            border: "1px solid rgba(255,255,255,0.12)",
            color: "var(--text-on-dark-muted)",
            fontFamily: "var(--font-body)",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "rgba(255,255,255,0.06)";
            e.currentTarget.style.color = "#FFFFFF";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
            e.currentTarget.style.color = "var(--text-on-dark-muted)";
          }}
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
