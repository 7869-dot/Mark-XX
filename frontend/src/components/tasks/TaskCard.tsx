import { useState } from "react";
import type { Task } from "@/types";
import { TaskStatusBadge } from "./TaskStatusBadge";
import { TimeAgo } from "@/components/ui/TimeAgo";
import { api } from "@/lib/api";

export function TaskCard({
  task,
  onChange,
}: {
  task: Task;
  onChange?: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [working, setWorking] = useState(false);

  const approve = async () => {
    setWorking(true);
    await api.approveTask(task.id);
    setWorking(false);
    onChange?.();
  };
  const reject = async () => {
    setWorking(true);
    await api.rejectTask(task.id);
    setWorking(false);
    onChange?.();
  };

  return (
    <div className="panel p-4">
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <TaskStatusBadge status={task.status} />
            <span className="chip border-ink-600 text-silver-axo">
              {task.task_type}
            </span>
            <span className="font-mono text-xs text-silver-axo/60 ml-auto">
              <TimeAgo iso={task.created_at} />
            </span>
          </div>
          <div className="font-display text-white text-sm leading-snug mb-1">
            {task.title}
          </div>
          <p className="font-mono text-xs text-silver-axo line-clamp-2">
            {task.result?.summary || task.description}
          </p>
        </div>
      </div>

      <button
        onClick={() => setExpanded((v) => !v)}
        className="font-mono text-[11px] text-silver-axo/70 hover:text-cyan-axo mt-2"
      >
        {expanded ? "Collapse" : "Expand"} ↓
      </button>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-ink-700/60 space-y-3 animate-fade-in">
          <div>
            <div className="label-mono mb-1">Description</div>
            <p className="font-mono text-xs text-silver-axo whitespace-pre-wrap">
              {task.description}
            </p>
          </div>
          {task.result && (
            <div>
              <div className="label-mono mb-1">Result</div>
              <p className="font-mono text-xs text-white whitespace-pre-wrap">
                {task.result.result || task.result.summary}
              </p>
              {task.result.recommended_action && (
                <div className="mt-2 panel-inset p-2">
                  <span className="label-mono">RECOMMENDED</span>
                  <p className="font-mono text-xs text-cyan-axo mt-1">
                    {task.result.recommended_action}
                  </p>
                </div>
              )}
            </div>
          )}
          {task.status === "awaiting_human" && (
            <div className="flex gap-2">
              <button onClick={approve} disabled={working} className="btn-primary text-xs py-1.5">
                Approve
              </button>
              <button onClick={reject} disabled={working} className="btn-danger text-xs py-1.5">
                Reject
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
