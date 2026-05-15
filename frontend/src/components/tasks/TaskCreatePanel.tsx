import { useState } from "react";
import { api } from "@/lib/api";
import { SlideOver } from "@/components/layout/SlideOver";

const TYPES = [
  { value: "research", label: "Research" },
  { value: "outreach", label: "Outreach" },
  { value: "scheduling", label: "Scheduling" },
  { value: "analysis", label: "Analysis" },
  { value: "networking", label: "Networking" },
  { value: "negotiation", label: "Negotiation" },
  { value: "monitoring", label: "Monitoring" },
];

export function TaskCreatePanel({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated?: () => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [taskType, setTaskType] = useState("research");
  const [requiresApproval, setRequiresApproval] = useState(false);
  const [priority, setPriority] = useState(3);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!title.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.createTask({
        title,
        description,
        task_type: taskType,
        priority,
        requires_human_approval: requiresApproval,
      });
      setTitle("");
      setDescription("");
      setTaskType("research");
      setRequiresApproval(false);
      setPriority(3);
      onCreated?.();
      onClose();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SlideOver open={open} onClose={onClose} title="DISPATCH NEW TASK">
      <div className="space-y-5">
        <div>
          <label className="label-mono block mb-2">Title</label>
          <input
            className="input w-full"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="What should your agent do?"
          />
        </div>

        <div>
          <label className="label-mono block mb-2">Description</label>
          <textarea
            className="input w-full min-h-[120px] resize-none"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Context, constraints, what 'done' looks like."
          />
        </div>

        <div>
          <label className="label-mono block mb-2">Task type</label>
          <div className="grid grid-cols-2 gap-2">
            {TYPES.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setTaskType(t.value)}
                className={`text-left px-3 py-2 rounded-md border text-xs font-mono transition ${
                  taskType === t.value
                    ? "border-cyan-axo/50 bg-cyan-axo/10 text-cyan-axo"
                    : "border-ink-600 text-silver-axo hover:border-ink-500"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="label-mono block mb-2">
            Priority — {priority}
          </label>
          <input
            type="range"
            min={1}
            max={5}
            value={priority}
            onChange={(e) => setPriority(Number(e.target.value))}
            className="w-full accent-cyan-axo"
          />
        </div>

        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={requiresApproval}
            onChange={(e) => setRequiresApproval(e.target.checked)}
            className="accent-cyan-axo"
          />
          <span className="font-mono text-xs text-silver-axo">
            Require my approval before acting on the result
          </span>
        </label>

        {error && (
          <div className="font-mono text-xs text-rose-axo">{error}</div>
        )}

        <div className="flex gap-2">
          <button
            disabled={!title.trim() || submitting}
            onClick={submit}
            className="btn-primary flex-1"
          >
            {submitting ? "Dispatching..." : "Dispatch task"}
          </button>
          <button onClick={onClose} className="btn-ghost">
            Cancel
          </button>
        </div>
      </div>
    </SlideOver>
  );
}
