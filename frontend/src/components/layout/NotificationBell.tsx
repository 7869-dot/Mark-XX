import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, Check } from "lucide-react";
import { api, type AppNotification } from "@/lib/api";

function relTime(iso: string | null): string {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

/** Navbar bell — unseen count badge + dropdown. Polls every 30s. */
export function NotificationBell() {
  const navigate = useNavigate();
  const [items, setItems] = useState<AppNotification[]>([]);
  const [unseen, setUnseen] = useState(0);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const load = async () => {
    try {
      const res = await api.notifications();
      setItems(res.items);
      setUnseen(res.unseen_count);
    } catch {
      /* ignore — pre-auth or transient */
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, []);

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const onItem = async (n: AppNotification) => {
    setItems((prev) => prev.filter((x) => x.id !== n.id));
    setUnseen((u) => Math.max(0, u - 1));
    try {
      await api.markNotificationSeen(n.id);
    } catch {
      /* best-effort */
    }
    setOpen(false);
    if (n.link) navigate(n.link);
  };

  const markAll = async () => {
    setItems([]);
    setUnseen(0);
    try {
      await api.markAllNotificationsSeen();
    } catch {
      /* best-effort */
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative inline-flex items-center justify-center w-9 h-9 rounded-full transition"
        style={{ color: "var(--text-secondary)" }}
        title="Notifications"
      >
        <Bell size={17} />
        {unseen > 0 && (
          <span
            className="absolute -top-0.5 -right-0.5 inline-flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full text-[9px] font-bold"
            style={{ background: "var(--accent-primary)", color: "#fff", fontFamily: "var(--font-data)" }}
          >
            {unseen > 9 ? "9+" : unseen}
          </span>
        )}
      </button>

      {open && (
        <div
          className="absolute right-0 mt-2 w-80 rounded-lg overflow-hidden z-50 shadow-xl"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}
        >
          <div
            className="flex items-center justify-between px-3 py-2"
            style={{ borderBottom: "1px solid var(--border)" }}
          >
            <span className="label-mono">Notifications</span>
            {items.length > 0 && (
              <button
                onClick={markAll}
                className="text-[11px] inline-flex items-center gap-1"
                style={{ color: "var(--text-secondary)", fontFamily: "var(--font-data)" }}
              >
                <Check size={11} /> Mark all read
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {items.length === 0 ? (
              <div className="px-3 py-6 text-center text-[12px]" style={{ color: "var(--text-muted)" }}>
                You're all caught up.
              </div>
            ) : (
              items.map((n) => (
                <button
                  key={n.id}
                  onClick={() => onItem(n)}
                  className="w-full text-left px-3 py-2.5 transition block"
                  style={{ borderBottom: "1px solid var(--border-subtle, var(--border))" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-base)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="inline-block w-1.5 h-1.5 rounded-full shrink-0"
                      style={{ background: "var(--accent-primary)" }}
                    />
                    <span
                      className="text-[12.5px] font-medium flex-1 min-w-0 truncate"
                      style={{ color: "var(--text-primary)", fontFamily: "var(--font-body)" }}
                    >
                      {n.title}
                    </span>
                    <span className="text-[10px] shrink-0" style={{ color: "var(--text-muted)", fontFamily: "var(--font-data)" }}>
                      {relTime(n.created_at)}
                    </span>
                  </div>
                  {n.body && (
                    <p className="text-[11.5px] mt-0.5 leading-snug pl-3.5" style={{ color: "var(--text-secondary)" }}>
                      {n.body}
                    </p>
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
