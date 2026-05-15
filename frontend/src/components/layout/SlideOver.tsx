import { useEffect, type ReactNode } from "react";

export function SlideOver({
  open,
  onClose,
  title,
  children,
  width = 480,
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  width?: number;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      <div
        className={`fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity ${
          open ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
        onClick={onClose}
      />
      <aside
        className={`fixed top-0 right-0 z-50 h-full bg-ink-900 border-l border-ink-600/60
                    shadow-2xl transition-transform duration-200 ease-out
                    w-full md:w-[var(--so-w)] ${
                      open ? "translate-x-0" : "translate-x-full"
                    }`}
        style={{ ["--so-w" as any]: `${width}px` }}
      >
        <div className="h-14 flex items-center justify-between px-5 border-b border-ink-700/70">
          <h2 className="font-display text-white text-sm tracking-wide">{title}</h2>
          <button
            onClick={onClose}
            className="text-silver-axo hover:text-white text-xl leading-none"
          >
            ×
          </button>
        </div>
        <div className="p-5 h-[calc(100%-3.5rem)] overflow-y-auto">{children}</div>
      </aside>
    </>
  );
}
