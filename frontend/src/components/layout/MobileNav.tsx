import { NavLink } from "react-router-dom";
import { Home, Mail, Calendar, Network, Sparkles } from "lucide-react";
import { useIntegrations } from "@/hooks/useIntegrations";
import { classNames } from "@/lib/utils";

const NAV = [
  { to: "/dashboard", label: "Home", icon: Home },
  { to: "/gmail", label: "Inbox", icon: Mail, badge: true },
  { to: "/calendar", label: "Calendar", icon: Calendar },
  { to: "/network", label: "Network", icon: Network },
  { to: "/jarvis", label: "Jarvis", icon: Sparkles },
];

export function MobileNav() {
  const { unread } = useIntegrations();

  return (
    <nav
      className="md:hidden fixed bottom-0 inset-x-0 z-40 h-14 flex"
      style={{
        background: "var(--bg-secondary)",
        borderTop: "1px solid var(--border)",
        boxShadow: "0 -4px 12px rgba(15,17,22,0.04)",
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
              fontFamily: "var(--font-body)",
              color: isActive ? "var(--accent-primary)" : "var(--text-secondary)",
            })}
          >
            <Icon size={16} />
            {item.label}
            {item.badge && unread > 0 && (
              <span
                className={classNames(
                  "absolute top-1.5 right-[28%] w-1.5 h-1.5 rounded-full"
                )}
                style={{ background: "var(--accent-primary)" }}
              />
            )}
          </NavLink>
        );
      })}
    </nav>
  );
}
