import { IconMail, IconWorld } from "@tabler/icons-react";
import type { EmailReport } from "@/lib/api";

/** The two agent summary cards under the briefing — real counts from the email
 *  triage and the web scout. */
export function AgentReportRow({
  emailReport,
  webCount,
}: {
  emailReport: EmailReport | null;
  webCount: number;
}) {
  const urgent = emailReport?.counts?.urgent ?? 0;
  const important = emailReport?.counts?.important ?? 0;
  const flagged = urgent + important;
  const connected = emailReport?.connected ?? false;

  return (
    <div className="axo-report-row">
      <div className="axo-report-card">
        <div className="axo-report-head email">
          <IconMail size={13} /> Email agent
        </div>
        <div className="axo-report-stat">{connected ? flagged : "—"}</div>
        <div className="axo-report-sub">{connected ? "flagged" : "not connected"}</div>
        {connected && flagged > 0 && (
          <div className="axo-badge-row">
            {urgent > 0 && <span className="axo-badge axo-badge-urgent">{urgent} urgent</span>}
            {important > 0 && <span className="axo-badge axo-badge-important">{important} important</span>}
          </div>
        )}
      </div>

      <div className="axo-report-card">
        <div className="axo-report-head web">
          <IconWorld size={13} /> Web agent
        </div>
        <div className="axo-report-stat">{webCount}</div>
        <div className="axo-report-sub">findings stored</div>
        {webCount > 0 && (
          <div className="axo-badge-row">
            <span className="axo-badge axo-badge-results">live web</span>
          </div>
        )}
      </div>
    </div>
  );
}
