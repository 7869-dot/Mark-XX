import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { CommandBar } from "./CommandBar";
import { MobileNav } from "./MobileNav";

export function AppShell() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <CommandBar />
        {/* pb-16 on mobile clears the fixed bottom nav */}
        <main className="flex-1 min-h-0 pb-16 md:pb-0">
          <Outlet />
        </main>
      </div>
      <MobileNav />
    </div>
  );
}
