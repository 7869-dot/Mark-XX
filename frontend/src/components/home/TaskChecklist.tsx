import { useState } from "react";
import { IconCheck } from "@tabler/icons-react";

/** Jarvis's suggested tasks for today (from the briefing's action_items).
 *  Check-off is local state only — no backend. */
export function TaskChecklist({ tasks }: { tasks: string[] }) {
  const [done, setDone] = useState<Record<number, boolean>>({});

  if (!tasks.length) {
    return <div className="axo-empty">Nothing flagged for today. Ask Jarvis what to focus on.</div>;
  }

  return (
    <>
      {tasks.map((t, i) => {
        const checked = !!done[i];
        return (
          <button
            key={i}
            className="axo-task-item"
            onClick={() => setDone((d) => ({ ...d, [i]: !d[i] }))}
          >
            <span className={`axo-task-check ${checked ? "done" : ""}`}>
              {checked && <IconCheck size={11} color="#fff" />}
            </span>
            <span className={`axo-task-text ${checked ? "done" : ""}`}>{t}</span>
          </button>
        );
      })}
    </>
  );
}
