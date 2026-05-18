import { apiRequest } from "@/lib/api";
import type { CalendarEvent, FreeSlot } from "./types";

export const calendarApi = {
  getEvents: (days = 7) =>
    apiRequest<CalendarEvent[]>(`/calendar/events?days=${days}`),

  getEvent: (id: string) =>
    apiRequest<CalendarEvent>(`/calendar/event/${id}`),

  getFreeSlots: (date: string, duration = 30) =>
    apiRequest<FreeSlot[]>(
      `/calendar/free-slots?date=${date}&duration=${duration}`
    ),

  createEvent: (data: {
    summary: string;
    start: string;
    end: string;
    description?: string;
    attendees?: string[];
    location?: string;
    meet_link?: boolean;
  }) =>
    apiRequest<{ id: string; meet_link: string }>("/calendar/event", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateEvent: (id: string, data: Record<string, unknown>) =>
    apiRequest<CalendarEvent>(`/calendar/event/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteEvent: (id: string, notify = true) =>
    apiRequest<{ deleted: boolean }>(
      `/calendar/event/${id}?notify=${notify}`,
      { method: "DELETE" }
    ),

  prepMeeting: (eventId: string) =>
    apiRequest<{ task_id: string; prep: { bullets: string[] } }>(
      "/agent/tasks/prep-meeting",
      { method: "POST", body: JSON.stringify({ event_id: eventId }) }
    ),

  dailyBriefing: () =>
    apiRequest<{ task_id: string; briefing: string }>(
      "/agent/tasks/daily-briefing",
      { method: "POST" }
    ),
};
