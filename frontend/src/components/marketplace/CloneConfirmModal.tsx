import { useEffect, useState } from "react";
import { api, type ClonePreview } from "@/lib/api";

/**
 * Two-column diff modal shown before applying a marketplace template.
 *
 * Fetches GET /marketplace/{id}/clone/preview on open and renders the
 * current-vs-after diff. "Replace my agent" calls onConfirm — the actual
 * POST /clone with `{ confirmed: true }` lives in the caller so the
 * caller controls the post-clone navigation / toast / refresh.
 */
export function CloneConfirmModal({
  templateId,
  templateName,
  onCancel,
  onConfirm,
  busy,
}: {
  templateId: string;
  templateName: string;
  onCancel: () => void;
  onConfirm: () => void;
  busy: boolean;
}) {
  const [preview, setPreview] = useState<ClonePreview | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    setPreview(null);
    setLoadError(false);
    api
      .marketplaceClonePreview(templateId)
      .then(setPreview)
      .catch(() => setLoadError(true));
  }, [templateId]);

  // Close on Escape so the modal feels native.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      style={{ background: "rgba(0,0,0,0.55)" }}
      onClick={onCancel}
    >
      <div
        className="panel p-6 w-full max-w-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <span className="label-mono">REPLACE AGENT?</span>
        <h2 className="font-display text-white text-xl mt-1 mb-1">
          Clone {templateName}
        </h2>
        <p className="font-mono text-xs text-coral-axo mb-5">
          {preview?.warning ||
            "This will overwrite your current agent configuration."}
        </p>

        {loadError && (
          <div className="panel p-4 mb-5 border-coral-axo/40">
            <p className="font-mono text-xs text-coral-axo">
              Couldn't load the preview. Try again.
            </p>
          </div>
        )}

        {!loadError && (
          <div className="grid grid-cols-2 gap-3 mb-6">
            <DiffColumn
              title="Current agent"
              tone="muted"
              rows={[
                ["Name", preview?.current.name ?? "—"],
                ["Bio", preview?.current.bio ?? "—"],
                [
                  "Auto-post",
                  preview?.current.auto_post_schedule ?? "—",
                ],
              ]}
            />
            <DiffColumn
              title="After cloning"
              tone="active"
              rows={[
                ["Name", preview?.after.name ?? "—"],
                ["Bio", preview?.after.bio ?? "—"],
                [
                  "Auto-post",
                  preview?.after.auto_post_schedule ?? "—",
                ],
              ]}
            />
          </div>
        )}

        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={busy}
            className="btn-ghost text-xs px-4 py-1.5"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={busy || (!preview && !loadError)}
            className="text-xs px-4 py-1.5 rounded-md font-display tracking-wide transition"
            style={{
              background: "var(--coral-bright, #ef4444)",
              color: "white",
              opacity: busy ? 0.6 : 1,
              border: "1px solid var(--coral-bright, #ef4444)",
            }}
          >
            {busy ? "Replacing…" : "Replace my agent"}
          </button>
        </div>
      </div>
    </div>
  );
}

function DiffColumn({
  title,
  tone,
  rows,
}: {
  title: string;
  tone: "muted" | "active";
  rows: [string, string][];
}) {
  return (
    <div
      className="panel p-4"
      style={
        tone === "active"
          ? { borderColor: "var(--border-active)" }
          : { opacity: 0.85 }
      }
    >
      <div
        className="font-display text-xs mb-3 tracking-wide"
        style={{
          color: tone === "active" ? "var(--teal-bright)" : "var(--text-muted)",
        }}
      >
        {title}
      </div>
      <dl className="space-y-2">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className="label-mono text-[10px]">{label}</dt>
            <dd className="font-mono text-xs text-silver-axo break-words mt-0.5">
              {value || "—"}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
