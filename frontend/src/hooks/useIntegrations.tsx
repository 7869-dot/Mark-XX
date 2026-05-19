/**
 * Shared integration state: Gmail/Calendar connection flags + unread badge.
 * Polls the unread count every 5 minutes (only while Gmail is connected).
 */
import { useEffect, useState } from "react";
import { integrationsApi } from "@/api/integrations";
import { gmailApi } from "@/api/gmail";
import type { IntegrationStatus } from "@/api/types";

export function useIntegrations() {
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    let alive = true;
    integrationsApi
      .getStatus()
      .then((s) => alive && setStatus(s))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!status || (!status.gmail && !status.stub_mode)) return;
    let alive = true;
    const tick = async () => {
      try {
        const list = await gmailApi.getInbox(true, 25);
        if (alive) setUnread(list.length);
      } catch {
        /* ignore */
      }
    };
    tick();
    const id = setInterval(tick, 5 * 60 * 1000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [status]);

  return {
    gmail: !!status?.gmail,
    calendar: !!status?.calendar,
    stubMode: !!status?.stub_mode,
    unread,
  };
}
