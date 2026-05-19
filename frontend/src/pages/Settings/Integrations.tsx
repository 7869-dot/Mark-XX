/**
 * Settings → Integrations.
 *
 * Connect/disconnect Gmail + Google Calendar. The "Connect" button asks the
 * backend for an authorization_url and hard-navigates to it; Google then
 * redirects back to this page with ?connected=google or ?error=true, which we
 * surface as a toast and then strip from the URL.
 */
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Mail, Calendar, Slack } from "lucide-react";
import { integrationsApi } from "@/api/integrations";
import type { IntegrationStatus } from "@/api/types";
import { IntegrationCard } from "@/components/settings/IntegrationCard";
import { pushToast } from "@/lib/toast";

export function IntegrationsSettingsPage() {
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [busy, setBusy] = useState<"gmail" | "calendar" | null>(null);
  const [params, setParams] = useSearchParams();

  const load = useCallback(async () => {
    try {
      setStatus(await integrationsApi.getStatus());
    } catch {
      /* error already toasted by the client */
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Handle the OAuth round-trip result.
  useEffect(() => {
    if (params.get("connected")) {
      pushToast(
        "Gmail & Calendar connected. Your agent will start triaging shortly.",
        "success"
      );
      params.delete("connected");
      setParams(params, { replace: true });
      load();
    } else if (params.get("error")) {
      pushToast("Connection failed. Please try again.", "error");
      params.delete("error");
      setParams(params, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const connect = async (which: "gmail" | "calendar") => {
    setBusy(which);
    try {
      const { authorization_url } =
        which === "gmail"
          ? await integrationsApi.connectGmail()
          : await integrationsApi.connectCalendar();
      window.location.href = authorization_url;
    } catch {
      setBusy(null);
    }
  };

  const disconnect = async (which: "gmail" | "calendar") => {
    setBusy(which);
    try {
      if (which === "gmail") await integrationsApi.disconnectGmail();
      else await integrationsApi.disconnectCalendar();
      pushToast(
        `${which === "gmail" ? "Gmail" : "Calendar"} disconnected.`,
        "info"
      );
      await load();
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <div className="mb-8">
        <span className="label-mono">SETTINGS</span>
        <h1 className="font-display text-white text-2xl mt-1">Integrations</h1>
        <p className="font-mono text-xs text-silver-axo mt-2">
          Connect your tools. Your agent acts on your behalf.
        </p>
      </div>

      {status?.stub_mode && (
        <div className="panel px-4 py-3 mb-5 border-amber-axo/40 bg-amber-axo/5">
          <p className="font-mono text-xs text-amber-axo">
            Stub mode — connecting uses a simulated Google account. Set real
            Google credentials and USE_STUBS=false for live mail/calendar.
          </p>
        </div>
      )}

      <div className="space-y-3">
        <IntegrationCard
          name="Gmail"
          description="Read, triage, draft, and send emails on your behalf"
          icon={<Mail size={20} />}
          isConnected={status?.gmail}
          busy={busy === "gmail"}
          lastSynced={
            status?.gmail && status.token_health.valid ? "just now" : null
          }
          onConnect={() => connect("gmail")}
          onDisconnect={() => disconnect("gmail")}
        />

        <IntegrationCard
          name="Google Calendar"
          description="See your schedule, find slots, book meetings, send invites"
          icon={<Calendar size={20} />}
          isConnected={status?.calendar}
          busy={busy === "calendar"}
          lastSynced={
            status?.calendar && status.token_health.valid ? "just now" : null
          }
          onConnect={() => connect("calendar")}
          onDisconnect={() => disconnect("calendar")}
        />

        <IntegrationCard
          name="Slack"
          description="Let your agent triage and respond to Slack messages"
          icon={<Slack size={20} />}
          comingSoon
        />
      </div>
    </div>
  );
}
