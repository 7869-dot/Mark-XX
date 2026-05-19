import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  Home,
  Mail,
  Calendar,
  Network,
  MoreHorizontal,
  User,
  ListChecks,
  Inbox,
  Settings,
} from "lucide-react";
import { useIntegrations } from "@/hooks/useIntegrations";
import { classNames } from "@/lib/utils";

const CORE = [
  { to: "/dashboard", label: "Home", icon: Home },
  { to: "/gmail", label: "Inbox", icon: Mail, badge: true },
  { to: "/calendar", label: "Calendar", icon: Calendar },
  { to: "/network", label: "Network", icon: Network },
];

const MORE = [
  { to: "/agent", label: "Agent", icon: User },
  { to: "/tasks", label: "Tasks", icon: ListChecks },
  { to: "/inbox", label: "Approvals", icon: Inbox },
  { to: "/settings/integrations", label: "Settings", icon: Settings },
];

export function MobileNav() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { unread } = useIntegrations();

  return (
    <>
      {open && (
        <>
          <div
            className="md:hidden fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />
          <div className="md:hidden fixed bottom-14 inset-x-0 z-50 panel m-2 p-2 animate-slide-in">
            {MORE.map((m) => {
              const Icon = m.icon;
              return (
                <button
                  key={m.to}
                  onClick={() => {
                    setOpen(false);
                    navigate(m.to);
                  }}
                  className="w-full flex items-center gap-3 px-3 py-3 rounded-md text-silver-axo hover:bg-ink-700/40 font-display text-sm"
                >
                  <Icon size={16} />
                  {m.label}
                </button>
              );
            })}
          </div>
        </>
      )}

      <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 h-14 bg-ink-900/95 backdrop-blur border-t border-ink-700/60 flex">
        {CORE.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                classNames(
                  "flex-1 flex flex-col items-center justify-center gap-0.5 text-[10px] font-mono transition relative",
                  isActive ? "text-cyan-axo" : "text-silver-axo"
                )
              }
            >
              <Icon size={16} />
              {item.label}
              {item.badge && unread > 0 && (
                <span className="absolute top-1.5 right-[28%] w-1.5 h-1.5 rounded-full bg-cyan-axo" />
              )}
            </NavLink>
          );
        })}
        <button
          onClick={() => setOpen((v) => !v)}
          className={classNames(
            "flex-1 flex flex-col items-center justify-center gap-0.5 text-[10px] font-mono transition",
            open ? "text-cyan-axo" : "text-silver-axo"
          )}
        >
          <MoreHorizontal size={16} />
          More
        </button>
      </nav>
    </>
  );
}
