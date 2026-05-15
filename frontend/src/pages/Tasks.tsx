import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { TaskCard } from "@/components/tasks/TaskCard";
import { TaskCreatePanel } from "@/components/tasks/TaskCreatePanel";
import { StatCard } from "@/components/ui/StatCard";
import { CountUp } from "@/components/ui/CountUp";
import type { AgentStats, Task } from "@/types";

const FILTERS = [
  { value: "", label: "All" },
  { value: "queued", label: "Queued" },
  { value: "running", label: "Running" },
  { value: "completed", label: "Completed" },
  { value: "awaiting_human", label: "Awaiting you" },
  { value: "rejected", label: "Rejected" },
];

export function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [filter, setFilter] = useState("");
  const [stats, setStats] = useState<AgentStats | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const load = async () => {
    const [t, s] = await Promise.all([api.myTasks(), api.getStats()]);
    setTasks(t);
    setStats(s);
  };

  useEffect(() => {
    load();
  }, []);

  const filtered = filter ? tasks.filter((t) => t.status === filter) : tasks;

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <span className="label-mono">TASK ENGINE</span>
          <h1 className="font-display text-white text-2xl mt-1">Task history</h1>
        </div>
        <button onClick={() => setCreateOpen(true)} className="btn-primary">
          + Dispatch task
        </button>
      </div>

      {/* The emotional hook — prominent, hours, this week, CountUp. */}
      <div className="panel p-6 md:p-8 text-center bg-gradient-to-b from-amber-axo/5 to-transparent border-amber-axo/30">
        <span className="label-mono">TIME RECLAIMED</span>
        <div className="mt-2 font-display text-white text-2xl md:text-3xl">
          Your agent has saved you{" "}
          <CountUp
            value={(stats?.time_saved_minutes_week ?? 0) / 60}
            decimals={1}
            className="text-amber-axo"
          />{" "}
          hours this week
        </div>
        <p className="font-mono text-xs text-silver-axo mt-2">
          {stats?.time_saved_minutes ?? 0} minutes saved all-time across{" "}
          {stats?.tasks_total ?? 0} completed tasks
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Total tasks" value={stats?.tasks_total ?? 0} />
        <StatCard label="This week" value={stats?.tasks_week ?? 0} />
        <StatCard
          label="Saved (all-time)"
          value={stats?.time_saved_minutes ?? 0}
          unit="min"
          tone="amber"
        />
        <StatCard label="Today" value={stats?.tasks_today ?? 0} tone="cyan" />
      </div>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`chip ${
              filter === f.value
                ? "border-cyan-axo/50 text-cyan-axo bg-cyan-axo/5"
                : "border-ink-600 text-silver-axo"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {filtered.length === 0 && (
          <div className="panel p-8 text-center">
            <p className="font-mono text-xs text-silver-axo">No tasks match this filter.</p>
          </div>
        )}
        {filtered.map((t) => (
          <TaskCard key={t.id} task={t} onChange={load} />
        ))}
      </div>

      <TaskCreatePanel
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={load}
      />
    </div>
  );
}
