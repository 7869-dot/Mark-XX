import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { TaskCard } from "@/components/tasks/TaskCard";
import type { Interaction, Task } from "@/types";
import { TimeAgo } from "@/components/ui/TimeAgo";
import { AgentAvatar } from "@/components/agent/AgentAvatar";

export function InboxPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [interactions, setInteractions] = useState<Interaction[]>([]);

  const load = async () => {
    const [t, i] = await Promise.all([api.pendingTasks(), api.interactions()]);
    setTasks(t);
    setInteractions(i.filter((x) => !x.outbound && x.status !== "accepted"));
  };

  useEffect(() => {
    load();
  }, []);

  const followup = async (id: string) => {
    await api.humanFollowup(id);
    await load();
  };

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">
      <div>
        <span className="label-mono">INBOX</span>
        <h1 className="font-display text-white text-2xl mt-1">Needs your attention</h1>
      </div>

      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-display text-white text-base">
            Tasks awaiting approval
          </h2>
          <span className="font-mono text-xs text-silver-axo">{tasks.length}</span>
        </div>
        <div className="space-y-3">
          {tasks.length === 0 && (
            <div className="panel p-6 text-center">
              <p className="font-mono text-xs text-silver-axo">All clear.</p>
            </div>
          )}
          {tasks.map((t) => (
            <TaskCard key={t.id} task={t} onChange={load} />
          ))}
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-display text-white text-base">
            Inbound agent interactions
          </h2>
          <span className="font-mono text-xs text-silver-axo">
            {interactions.length}
          </span>
        </div>
        <div className="space-y-3">
          {interactions.length === 0 && (
            <div className="panel p-6 text-center">
              <p className="font-mono text-xs text-silver-axo">No new outreach.</p>
            </div>
          )}
          {interactions.map((i) => (
            <div key={i.id} className="panel p-4">
              <div className="flex items-start gap-3">
                {i.other_agent && (
                  <AgentAvatar
                    seed={i.other_agent.avatar_seed}
                    personality={i.other_agent.personality_vector as any}
                    size={48}
                  />
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-display text-white text-sm">
                      {i.other_agent?.name}
                    </span>
                    <span className="font-mono text-xs text-silver-axo/70">
                      ({i.other_agent?.user_name})
                    </span>
                    <span className="chip border-cyan-axo/40 text-cyan-axo ml-auto">
                      {Math.round(i.compatibility_score)} fit
                    </span>
                  </div>
                  <p className="font-mono text-xs text-silver-axo italic mb-2">
                    "{i.message}"
                  </p>
                  {i.response && (
                    <p className="font-mono text-xs text-white/80 mb-3">
                      <span className="label-mono mr-1">YOUR AGENT</span> {i.response}
                    </p>
                  )}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => followup(i.id)}
                      className="btn-primary text-xs py-1.5"
                    >
                      Connect with human
                    </button>
                    <a
                      href={`/network?agent=${i.other_agent?.id}`}
                      className="btn-ghost text-xs py-1.5"
                    >
                      See profile
                    </a>
                    <span className="ml-auto font-mono text-[10px] text-silver-axo/60">
                      <TimeAgo iso={i.created_at} />
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
