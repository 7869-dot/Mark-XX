import { apiRequest } from "@/lib/api";
import type { EmailFull, EmailListItem, EmailThread, InboxSummary } from "./types";

export const gmailApi = {
  getInbox: (unreadOnly = false, max = 20) =>
    apiRequest<EmailListItem[]>(
      `/gmail/inbox?unread_only=${unreadOnly}&max=${max}`
    ),

  getEmail: (messageId: string) =>
    apiRequest<EmailFull>(`/gmail/email/${messageId}`),

  getThread: (threadId: string) =>
    apiRequest<EmailThread>(`/gmail/thread/${threadId}`),

  search: (q: string) =>
    apiRequest<EmailListItem[]>(`/gmail/search?q=${encodeURIComponent(q)}`),

  sendEmail: (to: string, subject: string, body: string, cc?: string) =>
    apiRequest<{ message_id: string }>("/gmail/send", {
      method: "POST",
      body: JSON.stringify({ to, subject, body, cc }),
    }),

  draftEmail: (to: string, subject: string, body: string, cc?: string) =>
    apiRequest<{ draft_id: string }>("/gmail/draft", {
      method: "POST",
      body: JSON.stringify({ to, subject, body, cc }),
    }),

  reply: (threadId: string, body: string, to?: string, subject?: string) =>
    apiRequest<{ message_id: string }>("/gmail/reply", {
      method: "POST",
      body: JSON.stringify({ thread_id: threadId, body, to, subject }),
    }),

  markRead: (messageId: string) =>
    apiRequest<{ ok: boolean }>(`/gmail/email/${messageId}/read`, {
      method: "PATCH",
    }),

  archive: (messageId: string) =>
    apiRequest<{ ok: boolean }>(`/gmail/email/${messageId}/archive`, {
      method: "PATCH",
    }),

  watchThread: (threadId: string) =>
    apiRequest<{ watched: boolean; id: string }>("/gmail/watch", {
      method: "POST",
      body: JSON.stringify({ thread_id: threadId }),
    }),

  summarizeInbox: () =>
    apiRequest<{ task_id: string; summary: InboxSummary }>(
      "/agent/tasks/summarize-inbox",
      { method: "POST" }
    ),

  draftReply: (messageId: string, instruction: string) =>
    apiRequest<{ task_id: string; draft_id: string; draft_body: string }>(
      "/agent/tasks/draft-reply",
      {
        method: "POST",
        body: JSON.stringify({ message_id: messageId, instruction }),
      }
    ),

  scheduleMeeting: (
    withEmail: string,
    purpose: string,
    duration = 30
  ) =>
    apiRequest<{
      task_id: string;
      draft_id: string;
      proposed_slots: { start: string; end: string }[];
      draft_body: string;
    }>("/agent/tasks/schedule-meeting", {
      method: "POST",
      body: JSON.stringify({ with_email: withEmail, purpose, duration }),
    }),
};
