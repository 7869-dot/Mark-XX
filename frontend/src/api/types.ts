export type TokenHealth = {
  valid: boolean;
  expires_in_minutes: number;
  stub?: boolean;
};

export type IntegrationStatus = {
  gmail: boolean;
  calendar: boolean;
  stub_mode: boolean;
  token_health: TokenHealth;
};

export type EmailListItem = {
  id: string;
  thread_id: string;
  subject: string;
  sender: string;
  sender_email: string;
  snippet: string;
  date: string;
  is_read: boolean;
  has_attachments: boolean;
  labels: string[];
};

export type EmailFull = EmailListItem & {
  to: string;
  cc: string;
  body_plain: string;
  body_html: string;
  attachments: { filename: string; mime_type: string; size: number }[];
};

export type EmailThread = {
  id: string;
  subject: string;
  messages: {
    id: string;
    subject: string;
    sender: string;
    sender_email: string;
    snippet: string;
    date: string;
  }[];
};

export type CalendarEvent = {
  id: string;
  summary: string;
  description: string;
  start: string;
  end: string;
  attendees: { name: string; email: string; status: string }[];
  location: string;
  meet_link: string;
  is_recurring: boolean;
  status: string;
};

export type FreeSlot = { start: string; end: string };

export type InboxSummary = {
  urgent?: { subject: string; from: string; suggested_reply?: string }[];
  important?: { subject: string; from: string; suggested_reply?: string }[];
  informational?: { subject: string; from: string }[];
  raw?: string;
};
