import { Outlet, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { Sidebar } from "./Sidebar";
import { CommandBar } from "./CommandBar";
import { MobileNav } from "./MobileNav";

export function AppShell() {
  const location = useLocation();
  return (
    <div className="flex min-h-screen" style={{ background: "var(--bg-void)" }}>
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <CommandBar />
        {/* pb-16 on mobile clears the fixed bottom nav */}
        <main className="flex-1 min-h-0 overflow-y-auto pb-16 md:pb-0">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
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
