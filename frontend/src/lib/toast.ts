export type Toast = {
  id: number;
  message: string;
  kind: "error" | "info" | "success";
};

type Listener = (toasts: Toast[]) => void;

let toasts: Toast[] = [];
let nextId = 1;
const listeners = new Set<Listener>();

function emit() {
  for (const l of listeners) l([...toasts]);
}

export function subscribe(l: Listener): () => void {
  listeners.add(l);
  l([...toasts]);
  return () => listeners.delete(l);
}

export function pushToast(message: string, kind: Toast["kind"] = "error") {
  const id = nextId++;
  toasts = [...toasts, { id, message, kind }];
  emit();
  setTimeout(() => dismissToast(id), 5000);
}

export function dismissToast(id: number) {
  toasts = toasts.filter((t) => t.id !== id);
  emit();
}
