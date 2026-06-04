import type { SubAgentStatus } from "@/lib/api";

/** Minimal agent health indicators (top right). Green = last run ok, grey =
 *  idle, red = failed. Jarvis (the orchestrator) is always live while the app
 *  is open; Web + Email come from GET /agents/status. Fetched on load only. */
const LABELS: Record<string, string> = {
  jarvis: "Jarvis",
  web_agent: "Web",
  email_agent: "Email",
};

function dotColor(status: string): string {
  const s = (status || "").toLowerCase();
  if (s === "ok" || s === "active" || s === "success") return "var(--accent-green)";
  if (s === "error" || s === "failed") return "var(--accent-red)";
  return "var(--text-tertiary)"; // idle / unknown
}

function Dot({ name, status, title }: { name: string; status: string; title: string }) {
  return (
    <div
      className="flex items-center gap-1.5"
      title={title}
      style={{ fontFamily: "var(--font-data)" }}
    >
      <span
        className="inline-block rounded-full"
        style={{ width: 7, height: 7, background: dotColor(status) }}
      />
      <span className="text-[11px]" style={{ color: "var(--text-secondary)" }}>
        {LABELS[name] || name}
      </span>
    </div>
  );
}

export function AgentStatusDots({ agents }: { agents: SubAgentStatus[] }) {
  const by = new Map(agents.map((a) => [a.agent_name, a]));
  const email = by.get("email_agent");
  const web = by.get("web_agent");
  const fmt = (a?: SubAgentStatus) =>
    a?.last_run
      ? `last run ${new Date(a.last_run).toLocaleString()} · ${a.status}`
      : "idle";

  return (
    <div className="flex items-center gap-3.5">
      <Dot name="jarvis" status="ok" title="Jarvis · orchestrator (live)" />
      <Dot name="web_agent" status={web?.status || "idle"} title={`Web Agent · ${fmt(web)}`} />
      <Dot name="email_agent" status={email?.status || "idle"} title={`Email Agent · ${fmt(email)}`} />
    </div>
  );
}
