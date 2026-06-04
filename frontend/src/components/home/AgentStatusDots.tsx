import type { SubAgentStatus } from "@/lib/api";

/** Nav agent pills — identity colour per agent (Jarvis green, Web blue, Email
 *  purple), overridden to red on a failed last run, dimmed when idle. Jarvis is
 *  the always-live orchestrator. Fetched on load (no live polling). */
function dotClass(identity: string, status?: string): string {
  const s = (status || "").toLowerCase();
  if (s === "error" || s === "failed") return "axo-dot axo-dot-red";
  if (s === "" || s === "idle") return "axo-dot axo-dot-idle";
  return `axo-dot ${identity}`;
}

function title(name: string, a?: SubAgentStatus): string {
  if (!a) return `${name} · idle`;
  const when = a.last_run ? new Date(a.last_run).toLocaleString() : "never";
  return `${name} · ${a.status} · last run ${when}`;
}

export function AgentStatusDots({ agents }: { agents: SubAgentStatus[] }) {
  const by = new Map(agents.map((a) => [a.agent_name, a]));
  const web = by.get("web_agent");
  const email = by.get("email_agent");

  return (
    <>
      <span className="axo-pill" title="Jarvis · orchestrator (live)">
        <span className="axo-dot axo-dot-green" />
        Jarvis
      </span>
      <span className="axo-pill" title={title("Web Agent", web)}>
        <span className={dotClass("axo-dot-blue", web?.status)} />
        Web
      </span>
      <span className="axo-pill" title={title("Email Agent", email)}>
        <span className={dotClass("axo-dot-purple", email?.status)} />
        Email
      </span>
    </>
  );
}
