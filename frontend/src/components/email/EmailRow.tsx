import type { EmailListItem } from "@/api/types";
import { TimeAgo } from "@/components/ui/TimeAgo";
import { classNames } from "@/lib/utils";

const TAG_TONE: Record<string, string> = {
  "Reply today": "border-rose-axo/40 text-rose-axo",
  "Decision needed": "border-amber-axo/40 text-amber-axo",
  Awaiting: "border-silver-axo/40 text-silver-axo",
  FYI: "border-ink-600 text-silver-axo/70",
};

function safeDate(d: string): string {
  const t = Date.parse(d);
  return isNaN(t) ? "" : new Date(t).toISOString();
}

export function EmailRow({
  email,
  onClick,
  isSelected,
  tag,
}: {
  email: EmailListItem;
  onClick: () => void;
  isSelected?: boolean;
  tag?: string;
}) {
  const iso = safeDate(email.date);
  return (
    <button
      onClick={onClick}
      className={classNames(
        "w-full text-left px-4 py-3 flex items-start gap-3 border-b border-ink-700/40 transition",
        isSelected ? "bg-ink-700/50" : "hover:bg-ink-800/60"
      )}
    >
      <span
        className={classNames(
          "mt-1.5 w-2 h-2 rounded-full shrink-0",
          email.is_read ? "border border-ink-500" : "bg-cyan-axo"
        )}
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span
            className={classNames(
              "text-sm truncate",
              email.is_read
                ? "text-silver-axo font-mono"
                : "text-white font-display"
            )}
          >
            {email.sender}
          </span>
          {tag && (
            <span className={classNames("chip ml-auto shrink-0", TAG_TONE[tag] || TAG_TONE.FYI)}>
              {tag}
            </span>
          )}
        </div>
        <div
          className={classNames(
            "text-sm truncate",
            email.is_read ? "text-silver-axo/80" : "text-white"
          )}
        >
          {email.subject || "(no subject)"}
        </div>
        <div className="font-mono text-xs text-silver-axo/60 truncate">
          {email.snippet.slice(0, 60)}
          {email.snippet.length > 60 ? "…" : ""}
        </div>
      </div>
      <span className="font-mono text-[10px] text-silver-axo/50 shrink-0">
        {iso ? <TimeAgo iso={iso} /> : email.date}
      </span>
    </button>
  );
}
