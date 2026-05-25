import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { TaskCreatePanel } from "@/components/tasks/TaskCreatePanel";
import { StatCard } from "@/components/ui/StatCard";
import { TaskStatusBadge } from "@/components/tasks/TaskStatusBadge";
import { IntegrationWidgets } from "@/components/dashboard/IntegrationWidgets";
import { EmailIntelligence } from "@/components/dashboard/EmailIntelligence";
import { AgentActivityLog } from "@/components/dashboard/AgentActivityLog";
import { AvailabilityPicker } from "@/components/agent/AvailabilityPicker";
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

  const active = tasks.filter(
    (t) => t.status === "running" || t.status === "queued"
  );
  const awaiting = tasks.filter((t) => t.status === "awaiting_human");

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[260px_minmax(0,1fr)_320px] gap-0 h-full">
      {/* LEFT — Availability + Stats column */}
      <div
        className="hidden xl:flex flex-col gap-3 p-4 overflow-y-auto"
        style={{ borderRight: "1px solid var(--border)" }}
      >
        <AvailabilityPicker />
        <span className="label-mono mt-2">Signal</span>
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

      {/* CENTER — Email Intelligence + Activity */}
      <div className="px-4 py-5 lg:px-8 lg:py-6 max-w-4xl w-full mx-auto overflow-y-auto">
        <div className="flex items-end justify-between mb-5">
          <div>
            <span className="label-mono">Command center</span>
            <h1
              className="text-3xl mt-1"
              style={{ fontFamily: "var(--font-display)" }}
            >
              {agent?.name}'s desk
            </h1>
          </div>
          <button onClick={() => setCreateOpen(true)} className="btn-primary">
            + Dispatch task
          </button>
        </div>
        <IntegrationWidgets />
        <EmailIntelligence />
        <AgentActivityLog />
      </div>

      {/* RIGHT — Queue + approvals */}
      <div
        className="hidden lg:flex flex-col gap-4 p-4 overflow-y-auto"
        style={{ borderLeft: "1px solid var(--border)" }}
      >
        <div>
          <span className="label-mono">Queue</span>
          <div className="mt-2 space-y-2">
            {active.length === 0 && (
              <p
                className="text-xs panel p-3"
                style={{
                  color: "var(--text-muted)",
                  fontFamily: "var(--font-data)",
                }}
              >
                Nothing in flight.
              </p>
            )}
            {active.map((t) => (
              <div key={t.id} className="panel p-3">
                <div className="flex items-center justify-between mb-1">
                  <TaskStatusBadge status={t.status} />
                  <span
                    className="text-[10px]"
                    style={{
                      color: "var(--text-muted)",
                      fontFamily: "var(--font-data)",
                    }}
                  >
                    {t.task_type}
                  </span>
                </div>
                <div
                  className="text-xs leading-tight"
                  style={{
                    fontFamily: "var(--font-body)",
                    color: "var(--text-primary)",
                  }}
                >
                  {t.title}
                </div>
              </div>
            ))}
          </div>
        </div>

        {awaiting.length > 0 && (
          <div>
            <span
              className="label-mono"
              style={{ color: "var(--accent-secondary)" }}
            >
              Awaiting you
            </span>
            <div className="mt-2 space-y-2">
              {awaiting.slice(0, 3).map((t) => (
                <a
                  key={t.id}
                  href="/inbox"
                  className="panel p-3 block transition"
                  style={{
                    borderColor: "var(--accent-secondary)",
                  }}
                >
                  <div
                    className="text-xs leading-tight"
                    style={{
                      fontFamily: "var(--font-body)",
                      color: "var(--text-primary)",
                    }}
                  >
                    {t.title}
                  </div>
                </a>
              ))}
            </div>
          </div>
        )}

        <div>
          <span className="label-mono">Upcoming jobs</span>
          <ul
            className="mt-2 panel p-3 text-[11px] space-y-1"
            style={{
              fontFamily: "var(--font-data)",
              color: "var(--text-secondary)",
            }}
          >
            <li>· Email classification — every 30m</li>
            <li>· A2A inbox sweep — every 5m</li>
            <li>· Heartbeat — every 15m</li>
            <li>· Goal check — daily 8:00</li>
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
