import { NavLink } from "react-router-dom";
import { Home, User, Network, ListChecks, Inbox, Mail, Calendar, Settings } from "lucide-react";
import { AgentAvatar } from "@/components/agent/AgentAvatar";
import { AgentStatusBadge } from "@/components/agent/AgentStatusBadge";
import { ReputationGauge } from "@/components/agent/ReputationGauge";
import { useAuth } from "@/hooks/useAuth";
import { useIntegrations } from "@/hooks/useIntegrations";
import { classNames } from "@/lib/utils";
import type { ReactNode } from "react";

const NAV: { to: string; label: string; icon: ReactNode; badge?: "unread" }[] = [
  { to: "/dashboard", label: "Command Center", icon: <Home size={16} /> },
  { to: "/gmail", label: "Inbox", icon: <Mail size={16} />, badge: "unread" },
  { to: "/calendar", label: "Calendar", icon: <Calendar size={16} /> },
  { to: "/agent", label: "Agent", icon: <User size={16} /> },
  { to: "/network", label: "Network", icon: <Network size={16} /> },
  { to: "/tasks", label: "Tasks", icon: <ListChecks size={16} /> },
  { to: "/inbox", label: "Approvals", icon: <Inbox size={16} /> },
  { to: "/settings/integrations", label: "Settings", icon: <Settings size={16} /> },
];

export function Sidebar() {
  const { agent, signOut } = useAuth();
  const { gmail, calendar, unread } = useIntegrations();
  if (!agent) return null;

  return (
    <aside className="hidden md:flex flex-col w-60 border-r border-ink-700/60 bg-ink-900/70 backdrop-blur-md">
      <div className="px-4 pt-5 pb-3 flex items-center gap-2">
        <div className="w-6 h-6 rounded-md bg-cyan-axo/20 border border-cyan-axo/40 flex items-center justify-center text-cyan-axo text-xs font-display">
          ax
        </div>
        <span className="font-display text-white tracking-wider text-sm">AXOLOT</span>
      </div>

      <div className="px-4 py-4 flex flex-col items-center gap-3 border-y border-ink-700/50">
        <AgentAvatar
          seed={agent.avatar_seed}
          personality={agent.personality_vector as any}
          size={72}
        />
        <div className="text-center">
          <div className="font-display text-white text-sm">{agent.name}</div>
          <div className="font-mono text-[11px] text-silver-axo/70">
            {agent.user_name}
          </div>
        </div>
        <AgentStatusBadge status={agent.status} />
        {/* connected-service pills */}
        <div className="flex gap-1.5">
          <span
            className={classNames(
              "chip",
              gmail
                ? "border-cyan-axo/40 text-cyan-axo"
                : "border-ink-600 text-silver-axo/50"
            )}
          >
            Gmail {gmail ? "✓" : "—"}
          </span>
          <span
            className={classNames(
              "chip",
              calendar
                ? "border-cyan-axo/40 text-cyan-axo"
                : "border-ink-600 text-silver-axo/50"
            )}
          >
            Cal {calendar ? "✓" : "—"}
          </span>
        </div>
        <ReputationGauge score={agent.reputation_score} size={96} />
      </div>

      <nav className="flex-1 p-3 flex flex-col gap-1 overflow-y-auto">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              classNames(
                "flex items-center gap-3 px-3 py-2 rounded-md font-display text-sm transition",
                isActive
                  ? "bg-cyan-axo/10 text-cyan-axo border border-cyan-axo/30"
                  : "text-silver-axo hover:text-white hover:bg-ink-700/40 border border-transparent"
              )
            }
          >
            <span className="leading-none">{item.icon}</span>
            <span className="flex-1">{item.label}</span>
            {item.badge === "unread" && unread > 0 && (
              <span className="chip border-cyan-axo/40 bg-cyan-axo/15 text-cyan-axo px-1.5">
                {unread > 99 ? "99+" : unread}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="p-3 border-t border-ink-700/50">
        <button onClick={signOut} className="btn-ghost w-full text-xs">
          Sign out
        </button>
      </div>
    </aside>
  );
}
