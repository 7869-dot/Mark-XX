import { NavLink } from "react-router-dom";
import { classNames } from "@/lib/utils";

const NAV = [
  { to: "/dashboard", label: "Home", icon: "◉" },
  { to: "/agent", label: "Agent", icon: "◈" },
  { to: "/network", label: "Network", icon: "◇" },
  { to: "/tasks", label: "Tasks", icon: "▤" },
  { to: "/inbox", label: "Inbox", icon: "✉" },
];

export function MobileNav() {
  return (
    <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 h-14 bg-ink-900/95 backdrop-blur border-t border-ink-700/60 flex">
      {NAV.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) =>
            classNames(
              "flex-1 flex flex-col items-center justify-center gap-0.5 text-[10px] font-mono transition",
              isActive ? "text-cyan-axo" : "text-silver-axo"
            )
          }
        >
          <span className="text-base leading-none">{item.icon}</span>
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
