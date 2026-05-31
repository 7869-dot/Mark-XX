import { useEffect, useState } from "react";
import { Copy, UserPlus, Check } from "lucide-react";
import { api } from "@/lib/api";
import { pushToast } from "@/lib/toast";

/** Sidebar growth widget — the user's invite link, copy button, invited count. */
export function InviteFriend() {
  const [code, setCode] = useState<string | null>(null);
  const [invited, setInvited] = useState(0);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const mine = await api.myInvites();
        setInvited(mine.invited_count);
        const unused = mine.items.find((i) => !i.used);
        if (unused) setCode(unused.code);
        else setCode((await api.generateInvite()).code);
      } catch {
        /* ignore */
      }
    })();
  }, []);

  const link = code ? `${window.location.origin}/join?code=${code}` : "";

  const copy = () => {
    if (!link) return;
    navigator.clipboard
      .writeText(link)
      .then(() => {
        setCopied(true);
        pushToast("Invite link copied", "success");
        setTimeout(() => setCopied(false), 1500);
      })
      .catch(() => pushToast(link));
  };

  return (
    <div className="panel p-3">
      <div className="flex items-center gap-1.5 mb-1">
        <UserPlus size={13} style={{ color: "var(--accent-primary)" }} />
        <span className="label-mono">Invite a friend</span>
      </div>
      <p className="text-[11px] mb-2.5" style={{ color: "var(--text-secondary)", fontFamily: "var(--font-body)" }}>
        Their agent gets a warm welcome from yours.
        {invited > 0 && (
          <> You've invited <span style={{ color: "var(--text-primary)" }}>{invited}</span> so far.</>
        )}
      </p>
      <div className="flex items-center gap-1.5">
        <input
          readOnly
          value={link}
          onFocus={(e) => e.currentTarget.select()}
          className="flex-1 min-w-0 text-[11px] px-2 py-1.5 rounded"
          style={{
            background: "var(--bg-base)",
            border: "1px solid var(--border)",
            color: "var(--text-secondary)",
            fontFamily: "var(--font-data)",
          }}
        />
        <button
          onClick={copy}
          disabled={!link}
          className="inline-flex items-center justify-center w-8 h-8 rounded shrink-0 transition"
          style={{ background: "var(--accent-primary)", color: "#fff", opacity: link ? 1 : 0.5 }}
          title="Copy invite link"
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
        </button>
      </div>
    </div>
  );
}
