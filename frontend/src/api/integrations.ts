import { apiRequest } from "@/lib/api";
import type { IntegrationStatus } from "./types";

export const integrationsApi = {
  getStatus: () => apiRequest<IntegrationStatus>("/integrations/status"),

  connectGmail: () =>
    apiRequest<{ authorization_url: string }>("/integrations/gmail/connect", {
      method: "POST",
    }),

  connectCalendar: () =>
    apiRequest<{ authorization_url: string }>("/integrations/calendar/connect", {
      method: "POST",
    }),

  disconnectGmail: () =>
    apiRequest<{ gmail: boolean; calendar: boolean }>(
      "/integrations/gmail/disconnect",
      { method: "POST" }
    ),

  disconnectCalendar: () =>
    apiRequest<{ gmail: boolean; calendar: boolean }>(
      "/integrations/calendar/disconnect",
      { method: "POST" }
    ),
};
