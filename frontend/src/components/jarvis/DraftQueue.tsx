import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { IconMail } from "@tabler/icons-react";
import { api, type AgentDraft } from "@/lib/api";
import { slideUp } from "@/lib/animations";
import { pushToast } from "@/lib/toast";

export function DraftQueue() {
  const [drafts, setDrafts] = useState<AgentDraft[] | null>(null);
  const [editing, setEditing] = useState<AgentDraft | null>(null);
  const [editText, setEditText] = useState("");

  const load = async () => {
    try {
      setDrafts((await api.agentDrafts()).items);
    } catch {
      setDrafts([]);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const decide = async (id: string, approved: boolean, content?: string) => {
    setDrafts((p) => p?.filter((d) => d.id !== id) ?? null);
    try {
      await api.decideDraft(id, approved, content);
      pushToast(approved ? "Draft approved (not sent — V1)" : "Draft killed", approved ? "success" : undefined);
    } catch {
      load();
    }
  };

  if (drafts === null || drafts.length === 0) return null; // hide when empty

  return (
    <section className="panel p-4 mt-5">
      <div className="label-mono mb-3">Drafts waiting on you</div>
      <motion.div className="space-y-2.5" initial={false}>
        <AnimatePresence>
          {drafts.map((d) => (
            <motion.div
              key={d.id}
              layout
              variants={slideUp}
              initial="hidden"
              animate="visible"
              exit={{ opacity: 0, height: 0, marginBottom: 0, transition: { duration: 0.25 } }}
              className="rounded-lg p-3 overflow-hidden"
              style={{ background: "var(--bg-elevated)" }}
            >
              <div className="flex items-center gap-2 mb-1">
                <IconMail size={14} style={{ color: "var(--accent-primary)" }} />
                <span className="text-[13px] font-medium" style={{ color: "var(--text-primary)" }}>
                  Draft ready — {d.recipient_hint}
                </span>
              </div>
              <div className="text-[12px] mb-1" style={{ color: "var(--text-secondary)" }}>
                Subject: {d.subject_line}
              </div>
              <p className="text-[12px] mb-2.5 leading-snug" style={{ color: "var(--text-muted)" }}>
                {d.draft_content.slice(0, 100)}
                {d.draft_content.length > 100 ? "…" : ""}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => { setEditing(d); setEditText(d.draft_content); }}
                  className="text-xs py-1 px-2.5 rounded"
                  style={{ border: "1px solid var(--border)", color: "var(--text-secondary)" }}
                >
                  View & Edit
                </button>
                <button onClick={() => decide(d.id, true)} className="btn-primary text-xs py-1 px-2.5">
                  Approve &amp; Send
                </button>
                <button
                  onClick={() => decide(d.id, false)}
                  className="text-xs py-1 px-2.5 rounded"
                  style={{ border: "1px solid var(--border)", color: "var(--text-muted)" }}
                >
                  Kill
                </button>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </motion.div>

      {/* Edit modal */}
      <AnimatePresence>
        {editing && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ background: "rgba(0,0,0,0.6)" }}
            onClick={() => setEditing(null)}
          >
            <motion.div
              initial={{ scale: 0.96, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.96, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="panel p-5 w-full max-w-lg"
            >
              <div className="label-mono mb-1">Edit draft — {editing.recipient_hint}</div>
              <div className="text-[13px] mb-3" style={{ color: "var(--text-secondary)" }}>
                Subject: {editing.subject_line}
              </div>
              <textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                rows={8}
                className="input w-full resize-none text-sm"
              />
              <div className="flex gap-2 mt-3 justify-end">
                <button
                  onClick={() => setEditing(null)}
                  className="text-xs py-1.5 px-3 rounded"
                  style={{ border: "1px solid var(--border)", color: "var(--text-secondary)" }}
                >
                  Cancel
                </button>
                <button
                  onClick={() => { decide(editing.id, true, editText); setEditing(null); }}
                  className="btn-primary text-xs py-1.5 px-3"
                >
                  Approve edited
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
