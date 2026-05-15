import { useEffect, useState } from "react";
import { subscribe, dismissToast, type Toast } from "@/lib/toast";

const TONE: Record<Toast["kind"], string> = {
  error: "border-rose-axo/50 text-rose-axo",
  info: "border-cyan-axo/40 text-cyan-axo",
  success: "border-cyan-axo/40 text-cyan-axo",
};

export function ToastContainer() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  useEffect(() => subscribe(setToasts), []);

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 max-w-sm">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`panel px-4 py-3 animate-slide-in flex items-start gap-3 ${TONE[t.kind]}`}
          role="alert"
        >
          <span className="font-mono text-xs leading-relaxed flex-1">
            {t.message}
          </span>
          <button
            onClick={() => dismissToast(t.id)}
            className="text-silver-axo hover:text-white leading-none"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
