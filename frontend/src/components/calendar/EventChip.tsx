import type { CalendarEvent } from "@/api/types";
import { classNames } from "@/lib/utils";

export type ColorCategory = "recurring" | "external" | "internal" | "personal";

const CHIP: Record<ColorCategory, string> = {
  recurring: "bg-[#7F77DD]/20 border-[#7F77DD]/50 text-[#b4aef0]",
  external: "bg-amber-axo/15 border-amber-axo/50 text-amber-axo",
  internal: "bg-cyan-axo/15 border-cyan-axo/40 text-cyan-axo",
  personal: "bg-ink-600/40 border-ink-500 text-silver-axo",
};

export function categorize(ev: CalendarEvent): ColorCategory {
  if (ev.is_recurring) return "recurring";
  const ext = (ev.attendees || []).some(
    (a) => a.email && !a.email.endsWith("@axolot.dev")
  );
  if (ext || ev.meet_link) return "external";
  if ((ev.attendees || []).length > 0) return "internal";
  return "personal";
}

export function EventChip({
  event,
  onClick,
  compact = false,
}: {
  event: CalendarEvent;
  onClick?: () => void;
  compact?: boolean;
}) {
  const cat = categorize(event);
  return (
    <button
      onClick={onClick}
      title={event.summary}
      className={classNames(
        "w-full text-left rounded border px-2 py-1 truncate transition hover:opacity-80",
        compact ? "text-[10px]" : "text-xs",
        CHIP[cat]
      )}
    >
      <span className="font-mono truncate">{event.summary}</span>
    </button>
  );
}
