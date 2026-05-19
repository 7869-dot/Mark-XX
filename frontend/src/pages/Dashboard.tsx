import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { ActivityFeed } from "@/components/feed/ActivityFeed";
import { TaskCreatePanel } from "@/components/tasks/TaskCreatePanel";
import { StatCard } from "@/components/ui/StatCard";
import { TaskStatusBadge } from "@/components/tasks/TaskStatusBadge";
import { IntegrationWidgets } from "@/components/dashboard/IntegrationWidgets";
import type { AgentStats, Task } from "@/types";

export function DashboardPage() {
  const { agent } = useAuth();
  const [stats, setStats] = useState<AgentStats | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [createOpen, setCreateOpen] = useState(false);

  const load = async () => {
    try {
      const [s, t] = await Promise.all([api.getStats(), api.myTasks()]);
      setStats(s);
      setTasks(t);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, []);

  const active = tasks.filter((t) => t.status === "running" || t.status === "queued");
  const awaiting = tasks.filter((t) => t.status === "awaiting_human");

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[280px_minmax(0,1fr)_320px] gap-0 min-h-[calc(100vh-3.5rem)]">
      {/* LEFT — Stats column */}
      <div className="hidden xl:flex flex-col gap-3 p-4 border-r border-ink-700/50">
        <span className="label-mono">SIGNAL</span>
        <StatCard label="Tasks today" value={stats?.tasks_today ?? 0} tone="cyan" />
        <StatCard label="This week" value={stats?.tasks_week ?? 0} />
        <StatCard label="All time" value={stats?.tasks_total ?? 0} />
        <StatCard label="Connections" value={stats?.connections ?? 0} />
        <StatCard
          label="Interactions today"
          value={stats?.interactions_today ?? 0}
          tone="cyan"
        />
        <StatCard
          label="Time saved"
          value={stats?.time_saved_minutes ?? 0}
          unit="min"
          tone="amber"
        />
      </div>

      {/* CENTER — Activity feed */}
      <div className="px-4 py-5 lg:px-8 lg:py-6 max-w-4xl w-full mx-auto">
        <div className="flex items-end justify-between mb-5">
          <div>
            <span className="label-mono">LIVE ACTIVITY</span>
            <h1 className="font-display text-white text-2xl mt-1">
              {agent?.name}'s feed
            </h1>
          </div>
          <button onClick={() => setCreateOpen(true)} className="btn-primary">
            + Dispatch task
          </button>
        </div>
        <IntegrationWidgets />
        <ActivityFeed />
      </div>

      {/* RIGHT — Queue + quick create */}
      <div className="hidden lg:flex flex-col gap-4 p-4 border-l border-ink-700/50">
        <div>
          <span className="label-mono">QUEUE</span>
          <div className="mt-2 space-y-2">
            {active.length === 0 && (
              <p className="font-mono text-xs text-silver-axo/60 panel p-3">
                Nothing in flight.
              </p>
            )}
            {active.map((t) => (
              <div key={t.id} className="panel p-3">
                <div className="flex items-center justify-between mb-1">
                  <TaskStatusBadge status={t.status} />
                  <span className="font-mono text-[10px] text-silver-axo/60">
                    {t.task_type}
                  </span>
                </div>
                <div className="font-display text-white text-xs leading-tight">
                  {t.title}
                </div>
              </div>
            ))}
          </div>
        </div>

        {awaiting.length > 0 && (
          <div>
            <span className="label-mono text-amber-axo">AWAITING YOU</span>
            <div className="mt-2 space-y-2">
              {awaiting.slice(0, 3).map((t) => (
                <a
                  key={t.id}
                  href="/inbox"
                  className="panel p-3 block border-amber-axo/30 hover:border-amber-axo/50 transition"
                >
                  <div className="font-display text-white text-xs leading-tight">
                    {t.title}
                  </div>
                </a>
              ))}
            </div>
          </div>
        )}

        <div>
          <span className="label-mono">UPCOMING JOBS</span>
          <ul className="mt-2 panel p-3 font-mono text-[11px] text-silver-axo space-y-1">
            <li>· Heartbeat — every 15m</li>
            <li>· Goal check — daily 8:00</li>
            <li>· Network scan — every 6h</li>
            <li>· Daily digest — 19:00</li>
          </ul>
        </div>
      </div>

      <TaskCreatePanel
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={load}
      />
    </div>
  );
}
