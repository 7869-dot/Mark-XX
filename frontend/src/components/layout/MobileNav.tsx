import { NavLink } from "react-router-dom";
import { Home, Mail, Calendar, Network, MessageSquare } from "lucide-react";
import { useIntegrations } from "@/hooks/useIntegrations";
import { classNames } from "@/lib/utils";

const NAV = [
  { to: "/dashboard", label: "Home", icon: Home },
  { to: "/gmail", label: "Inbox", icon: Mail, badge: true },
  { to: "/calendar", label: "Calendar", icon: Calendar },
  { to: "/network", label: "Network", icon: Network },
  { to: "/chat", label: "Chat", icon: MessageSquare },
];

export function MobileNav() {
  const { unread } = useIntegrations();

  return (
    <nav
      className="md:hidden fixed bottom-0 inset-x-0 z-40 h-14 flex"
      style={{
        background: "var(--bg-surface)",
        borderTop: "1px solid var(--border-subtle)",
        backdropFilter: "blur(8px)",
      }}
    >
      {NAV.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.to}
            to={item.to}
            className="flex-1 flex flex-col items-center justify-center gap-0.5 text-[10px] transition relative"
            style={({ isActive }) => ({
              fontFamily: "var(--font-data)",
              color: isActive ? "var(--teal-bright)" : "var(--text-secondary)",
            })}
          >
            <Icon size={16} />
            {item.label}
            {item.badge && unread > 0 && (
              <span
                className={classNames(
                  "absolute top-1.5 right-[28%] w-1.5 h-1.5 rounded-full"
                )}
                style={{ background: "var(--teal-bright)" }}
              />
            )}
          </NavLink>
        );
      })}
    </nav>
  );
}
