/** Compact toggle for the active agent's availability window.
 *
 * Three states: always_on (green), business_hours (gold), dnd (grey). Lives
 * on the dashboard and the agent profile page. Persists immediately to the
 * backend via /agent/availability — no save button.
 */
import { useEffect, useState } from "react";
import { api, type AgentAvailabilityValue } from "@/lib/api";
import { pushToast } from "@/lib/toast";

const OPTIONS: {
  value: AgentAvailabilityValue;
  label: string;
  dot: string;
  /** Background when this option is selected. DND gets the danger red per spec. */
  activeBg: string;
  activeColor: string;
}[] = [
  {
    value: "always_on",
    label: "Always on",
    dot: "var(--accent-green)",
    activeBg: "var(--accent-blue)",
    activeColor: "var(--text-on-accent)",
  },
  {
    value: "business_hours",
    label: "Business hours",
    dot: "var(--accent-gold)",
    activeBg: "var(--accent-blue)",
    activeColor: "var(--text-on-accent)",
  },
  {
    value: "dnd",
    label: "Do not disturb",
    dot: "var(--text-tertiary)",
    activeBg: "var(--accent-red)",
    activeColor: "var(--text-on-accent)",
  },
];

export function AvailabilityPicker() {
  const [value, setValue] = useState<AgentAvailabilityValue | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .getAvailability()
      .then((res) => setValue(res.availability))
      .catch(() => setValue("always_on"));
  }, []);

  const choose = async (next: AgentAvailabilityValue) => {
    if (next === value) return;
    setSaving(true);
    setValue(next);
    try {
      await api.setAvailability(next);
      pushToast(`Availability: ${OPTIONS.find((o) => o.value === next)?.label}`);
    } catch {
      /* toast already pushed; let the error propagate by reverting */
      const prev = value;
      setValue(prev);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="panel p-3">
      <div
        className="text-[11px] uppercase tracking-wider mb-2"
        style={{
          color: "var(--text-secondary)",
          fontFamily: "var(--font-data)",
        }}
      >
        Agent availability
      </div>
      <div className="flex gap-1.5">
        {OPTIONS.map((o) => {
          const active = o.value === value;
          return (
            <button
              key={o.value}
              onClick={() => choose(o.value)}
              disabled={saving}
              className="flex-1 text-[12px] px-2.5 py-1.5 rounded-md inline-flex items-center justify-center gap-1.5 transition"
              style={{
                background: active ? o.activeBg : "var(--bg-elevated)",
                border: active
                  ? `1px solid ${o.activeBg}`
                  : "1px solid var(--border-default)",
                color: active ? o.activeColor : "var(--text-secondary)",
                fontFamily: "var(--font-body)",
                fontWeight: active ? 600 : 400,
              }}
            >
              <span
                className="inline-block w-1.5 h-1.5 rounded-full"
                style={{ background: active ? o.activeColor : o.dot }}
              />
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
