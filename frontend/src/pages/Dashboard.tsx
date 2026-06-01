import { useState } from "react";
import { motion } from "framer-motion";
import { useAuth } from "@/hooks/useAuth";
import { TaskCreatePanel } from "@/components/tasks/TaskCreatePanel";
import { AgentSuggestions } from "@/components/dashboard/AgentSuggestions";
import { AgentTeam } from "@/components/dashboard/AgentTeam";
import { InviteFriend } from "@/components/dashboard/InviteFriend";
import { JarvisPanel } from "@/components/jarvis/JarvisPanel";
import { DraftQueue } from "@/components/jarvis/DraftQueue";
import { IslandsPulse } from "@/components/jarvis/IslandsPulse";
import { fadeUp } from "@/lib/animations";

/**
 * Home — Jarvis-first. Left column: Jarvis briefing + the drafts it queued.
 * Right column: the live pulse of the network. No vanity metrics — the platform
 * does, it doesn't report doing.
 */
export function DashboardPage() {
  const { agent } = useAuth();
  const [createOpen, setCreateOpen] = useState(false);

  return (
    <motion.div
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className="h-full overflow-y-auto"
    >
      <div className="max-w-5xl mx-auto px-4 py-6 lg:px-8">
        <div className="flex items-end justify-between mb-5">
          <div>
            <span className="label-mono">Home</span>
            <h1 className="text-2xl mt-1" style={{ fontFamily: "var(--font-display)" }}>
              {agent?.name ? `${agent.name}'s desk` : "Your desk"}
            </h1>
          </div>
          <button onClick={() => setCreateOpen(true)} className="btn-primary text-sm">
            + Dispatch task
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] gap-5">
          {/* LEFT — Jarvis + drafts + suggestions */}
          <div>
            <JarvisPanel />
            <DraftQueue />
            <div className="mt-5">
              <AgentSuggestions />
            </div>
          </div>

          {/* RIGHT — Islands pulse + team + invite */}
          <div className="flex flex-col gap-5">
            <IslandsPulse />
            <AgentTeam />
            <InviteFriend />
          </div>
        </div>
      </div>

      <TaskCreatePanel open={createOpen} onClose={() => setCreateOpen(false)} onCreated={() => {}} />
    </motion.div>
  );
}
