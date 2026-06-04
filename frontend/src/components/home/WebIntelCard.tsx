import { IconExternalLink } from "@tabler/icons-react";
import type { WebFind } from "@/lib/api";

function hostname(u: string): string {
  try {
    return new URL(u).hostname.replace(/^www\./, "");
  } catch {
    return u;
  }
}

export function WebIntelCard({ find }: { find: WebFind }) {
  return (
    <a
      href={find.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block rounded-xl p-3.5 transition"
      style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium leading-snug" style={{ color: "var(--text-primary)" }}>
          {find.title}
        </span>
        <IconExternalLink
          size={14}
          className="shrink-0 mt-0.5"
          style={{ color: "var(--text-tertiary)" }}
        />
      </div>
      <p className="text-[13px] mt-1.5 leading-relaxed line-clamp-2" style={{ color: "var(--text-secondary)" }}>
        {find.summary}
      </p>
      <div className="flex items-center gap-2 mt-2">
        {find.category && (
          <span
            className="text-[10px] px-1.5 py-0.5 rounded"
            style={{
              background: "var(--bg-elevated)",
              color: "var(--text-secondary)",
              fontFamily: "var(--font-data)",
            }}
          >
            {find.category}
          </span>
        )}
        <span
          className="text-[11px] truncate"
          style={{ color: "var(--accent-primary)", fontFamily: "var(--font-data)" }}
        >
          {hostname(find.url)}
        </span>
      </div>
    </a>
  );
}
