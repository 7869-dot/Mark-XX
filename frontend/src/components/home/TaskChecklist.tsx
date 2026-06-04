import { useState } from "react";
import { IconCheck } from "@tabler/icons-react";

/** Jarvis's suggested tasks for today (from the briefing's action_items).
 *  Check-off is local state only — no backend. */
export function TaskChecklist({ tasks }: { tasks: string[] }) {
  const [done, setDone] = useState<Record<number, boolean>>({});

  if (!tasks.length) {
    return (
      <p className="text-sm px-1 py-6 text-center" style={{ color: "var(--text-secondary)" }}>
        Nothing flagged for today. Ask Jarvis what to focus on.
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {tasks.map((t, i) => {
        const checked = !!done[i];
        return (
          <li key={i}>
            <button
              onClick={() => setDone((d) => ({ ...d, [i]: !d[i] }))}
              className="w-full text-left flex items-start gap-3 rounded-xl px-3 py-2.5 transition"
              style={{
                background: "var(--bg-surface)",
                border: "1px solid var(--border)",
              }}
            >
              <span
                className="mt-0.5 shrink-0 rounded-md inline-flex items-center justify-center"
                style={{
                  width: 18,
                  height: 18,
                  border: `1px solid ${checked ? "var(--accent-green)" : "var(--border-strong)"}`,
                  background: checked ? "var(--accent-green)" : "transparent",
                }}
              >
                {checked && <IconCheck size={13} color="#fff" />}
              </span>
              <span
                className="text-sm leading-snug"
                style={{
                  color: checked ? "var(--text-secondary)" : "var(--text-primary)",
                  textDecoration: checked ? "line-through" : "none",
                }}
              >
                {t}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
