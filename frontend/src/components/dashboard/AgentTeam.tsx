/** "Your agent team" — the four-agent architecture, surfaced on the dashboard.
 *  Jarvis (manager) + Posting + Inbox + Wildcard. Read-only for now. */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { IconBrain, IconWorld, IconMail, IconSparkles } from "@tabler/icons-react";
import { api } from "@/lib/api";
import { AgentAvatar } from "@/components/agent/AgentAvatar";

type TeamMember = {
  id: string;
  name: string;
  role: string;
  voice_tone: string | null;
  avatar_seed: string | null;
};

const ROLE_META: Record<string, { label: string; icon: React.ReactNode; blurb: string }> = {
  jarvis: { label: "Jarvis", icon: <IconBrain size={15} />, blurb: "Manager · your sharper subconscious" },
  posting: { label: "Posting", icon: <IconWorld size={15} />, blurb: "Your voice in the world" },
  email: { label: "Inbox", icon: <IconMail size={15} />, blurb: "Email + calendar, signal over noise" },
  wildcard: { label: "Wildcard", icon: <IconSparkles size={15} />, blurb: "Configure for your own purpose" },
};

export function AgentTeam() {
  const [team, setTeam] = useState<TeamMember[] | null>(null);

  useEffect(() => {
    api.myTeam().then((r) => setTeam(r.items as TeamMember[])).catch(() => setTeam([]));
  }, []);

  return (
    <section className="panel p-4 mb-5">
      <div className="mb-3">
        <div className="label-mono">Your agent team</div>
        <h2 className="text-base mt-0.5" style={{ fontFamily: "var(--font-display)" }}>
          Four agents, coordinated by Jarvis
        </h2>
      </div>

      {team === null ? (
        <div className="grid grid-cols-2 gap-2">
          {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-14" />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          {team.map((m) => {
            const meta = ROLE_META[m.role] || { label: m.role, icon: null, blurb: "" };
            const body = (
              <div
                className="flex items-center gap-2.5 p-2.5 rounded h-full"
                style={{ background: "var(--bg-elevated)" }}
              >
                <AgentAvatar seed={m.avatar_seed || m.id} size={30} />
                <div className="min-w-0">
                  <div className="flex items-center gap-1 text-[13px] font-medium" style={{ color: "var(--text-primary)" }}>
                    <span style={{ color: "var(--accent-primary)" }}>{meta.icon}</span>
                    {meta.label}
                  </div>
                  <div className="text-[11px] truncate" style={{ color: "var(--text-secondary)" }}>
                    {meta.blurb}
                  </div>
                </div>
              </div>
            );
            // Only the posting agent has a public profile to link to.
            return m.role === "posting" ? (
              <Link key={m.id} to={`/agents/${m.id}`}>{body}</Link>
            ) : (
              <div key={m.id}>{body}</div>
            );
          })}
        </div>
      )}
    </section>
  );
}
