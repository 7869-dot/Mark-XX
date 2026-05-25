import { Outlet, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { Sidebar } from "./Sidebar";
import { CommandBar } from "./CommandBar";
import { MobileNav } from "./MobileNav";

export function AppShell() {
  const location = useLocation();
  return (
    <div className="flex h-screen" style={{ background: "var(--bg-primary)" }}>
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <CommandBar />
        {/* pb-16 on mobile clears the fixed bottom nav. min-h-0 is required so
            flex children can actually shrink and the inner overflow-y-auto
            takes effect — without it, the page grows unbounded. */}
        <main
          className="flex-1 min-h-0 overflow-y-auto pb-16 md:pb-0"
          style={{ background: "var(--bg-primary)" }}
        >
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="h-full"
          >
            <Outlet />
          </motion.div>
        </main>
      </div>
      <MobileNav />
    </div>
  );
}
