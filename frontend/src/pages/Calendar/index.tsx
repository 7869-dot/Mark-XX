/**
 * Calendar — custom week grid (no calendar library).
 *
 * 8am–7pm, 30-min rows. Events absolutely positioned per day column. Clicking
 * an event opens a slide-over with inline agent prep. Not connected → CTA.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, ChevronRight, CalendarPlus, ExternalLink } from "lucide-react";
import { calendarApi } from "@/api/calendar";
import { integrationsApi } from "@/api/integrations";
import type { CalendarEvent, FreeSlot } from "@/api/types";
import { EventChip, categorize } from "@/components/calendar/EventChip";
import { AgentBanner } from "@/components/shared/AgentBanner";
import { SlideOver } from "@/components/layout/SlideOver";
import { pushToast } from "@/lib/toast";

const DAY_START = 8; // 8am
const DAY_END = 19; // 7pm
const ROW_MIN = 30;
const ROWS = ((DAY_END - DAY_START) * 60) / ROW_MIN;
const PX_PER_MIN = 0.9;

function startOfWeek(d: Date): Date {
  const x = new Date(d);
  const day = (x.getDay() + 6) % 7; // Monday-based
  x.setDate(x.getDate() - day);
  x.setHours(0, 0, 0, 0);
  return x;
}

function parse(dt: string): Date | null {
  const t = Date.parse(dt);
  return isNaN(t) ? null : new Date(t);
}

export function CalendarPage() {
  const navigate = useNavigate();
  const [connected, setConnected] = useState<boolean | null>(null);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const [selected, setSelected] = useState<CalendarEvent | null>(null);
  const [scheduleOpen, setScheduleOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      const st = await integrationsApi.getStatus();
      setConnected(st.calendar || st.stub_mode);
      if (st.calendar || st.stub_mode) {
        setEvents(await calendarApi.getEvents(14));
      }
    } catch {
      setConnected(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const days = useMemo(
    () =>
      Array.from({ length: 7 }, (_, i) => {
        const d = new Date(weekStart);
        d.setDate(d.getDate() + i);
        return d;
      }),
    [weekStart]
  );

  const today = new Date();

  if (connected === false) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-8">
        <h1 className="font-display text-white text-2xl mb-4">Calendar</h1>
        <AgentBanner
          variant="warning"
          text="Connect Google Calendar to see your schedule and let your agent book meetings."
          actionLabel="Connect"
          onAction={() => navigate("/settings/integrations")}
        />
      </div>
    );
  }

  const todays = events.filter((e) => {
    const s = parse(e.start);
    return s && s.toDateString() === today.toDateString();
  });

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col">
      <div className="flex items-center justify-between px-6 py-4 border-b border-ink-700/50">
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              const d = new Date(weekStart);
              d.setDate(d.getDate() - 7);
              setWeekStart(d);
            }}
            className="btn-ghost text-xs px-2 py-1"
          >
            <ChevronLeft size={14} />
          </button>
          <span className="font-display text-white text-sm">
            Week of{" "}
            {weekStart.toLocaleDateString(undefined, {
              month: "short",
              day: "numeric",
            })}
          </span>
          <button
            onClick={() => {
              const d = new Date(weekStart);
              d.setDate(d.getDate() + 7);
              setWeekStart(d);
            }}
            className="btn-ghost text-xs px-2 py-1"
          >
            <ChevronRight size={14} />
          </button>
        </div>
        <button
          onClick={() => setScheduleOpen(true)}
          className="btn-primary text-xs"
        >
          <CalendarPlus size={13} className="inline mr-1" /> Schedule with agent
        </button>
      </div>

      {todays.length > 0 && (
        <div className="px-6 pt-4">
          <AgentBanner
            variant="info"
            text={`Today: ${todays.length} meeting${
              todays.length === 1 ? "" : "s"
            }. ${todays[0].summary} at ${parse(todays[0].start)?.toLocaleTimeString(
              [],
              { hour: "2-digit", minute: "2-digit" }
            )}.`}
            actionLabel="Open"
            onAction={() => setSelected(todays[0])}
          />
        </div>
      )}

      {/* Week grid */}
      <div className="flex-1 overflow-auto p-4">
        <div className="grid grid-cols-[48px_repeat(7,minmax(110px,1fr))] min-w-[760px]">
          <div />
          {days.map((d) => {
            const isToday = d.toDateString() === today.toDateString();
            return (
              <div
                key={d.toISOString()}
                className={`text-center pb-2 ${
                  isToday ? "text-cyan-axo" : "text-silver-axo"
                }`}
              >
                <div className="font-mono text-[10px] uppercase tracking-wider">
                  {d.toLocaleDateString(undefined, { weekday: "short" })}
                </div>
                <div className="font-display text-sm">{d.getDate()}</div>
              </div>
            );
          })}

          {/* time gutter */}
          <div className="relative" style={{ height: ROWS * ROW_MIN * PX_PER_MIN }}>
            {Array.from({ length: DAY_END - DAY_START }, (_, i) => (
              <div
                key={i}
                className="absolute right-1 font-mono text-[9px] text-silver-axo/50"
                style={{ top: i * 60 * PX_PER_MIN - 5 }}
              >
                {DAY_START + i}:00
              </div>
            ))}
          </div>

          {days.map((d) => (
            <div
              key={d.toISOString()}
              className="relative border-l border-ink-700/40"
              style={{ height: ROWS * ROW_MIN * PX_PER_MIN }}
            >
              {Array.from({ length: ROWS }, (_, r) => (
                <div
                  key={r}
                  className="absolute inset-x-0 border-t border-ink-700/20"
                  style={{ top: r * ROW_MIN * PX_PER_MIN }}
                />
              ))}
              {events
                .filter((e) => {
                  const s = parse(e.start);
                  return s && s.toDateString() === d.toDateString();
                })
                .map((e) => {
                  const s = parse(e.start)!;
                  const en = parse(e.end) || new Date(s.getTime() + 30 * 60000);
                  const top =
                    ((s.getHours() - DAY_START) * 60 + s.getMinutes()) *
                    PX_PER_MIN;
                  const height = Math.max(
                    18,
                    ((en.getTime() - s.getTime()) / 60000) * PX_PER_MIN
                  );
                  return (
                    <div
                      key={e.id}
                      className="absolute inset-x-1"
                      style={{ top: Math.max(0, top), height }}
                    >
                      <div className="h-full overflow-hidden">
                        <EventChip
                          event={e}
                          compact
                          onClick={() => setSelected(e)}
                        />
                      </div>
                    </div>
                  );
                })}
            </div>
          ))}
        </div>
      </div>

      <EventDetailSlideOver
        event={selected}
        onClose={() => setSelected(null)}
        onChanged={load}
      />

      <SlideOver
        open={scheduleOpen}
        onClose={() => setScheduleOpen(false)}
        title="SCHEDULE WITH AGENT"
        width={460}
      >
        <ScheduleMeetingForm
          onDone={() => {
            setScheduleOpen(false);
            load();
          }}
        />
      </SlideOver>
    </div>
  );
}

function EventDetailSlideOver({
  event,
  onClose,
  onChanged,
}: {
  event: CalendarEvent | null;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [prep, setPrep] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setPrep(null);
  }, [event?.id]);

  if (!event) return null;

  const start = parse(event.start);
  const end = parse(event.end);

  const genPrep = async () => {
    setBusy(true);
    try {
      const res = await calendarApi.prepMeeting(event.id);
      setPrep(res.prep.bullets || []);
    } finally {
      setBusy(false);
    }
  };

  const del = async () => {
    if (!confirm(`Delete "${event.summary}"?`)) return;
    await calendarApi.deleteEvent(event.id);
    pushToast("Event deleted.", "info");
    onClose();
    onChanged();
  };

  return (
    <SlideOver open={!!event} onClose={onClose} title="EVENT" width={440}>
      <div className="space-y-5">
        <div>
          <div className="font-display text-white text-lg">{event.summary}</div>
          <div className="font-mono text-xs text-silver-axo mt-1">
            {start?.toLocaleString([], {
              weekday: "short",
              hour: "2-digit",
              minute: "2-digit",
            })}{" "}
            – {end?.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </div>
          <span
            className={`chip mt-2 inline-block ${
              categorize(event) === "external"
                ? "border-amber-axo/40 text-amber-axo"
                : "border-cyan-axo/40 text-cyan-axo"
            }`}
          >
            {categorize(event)}
          </span>
        </div>

        {event.attendees.length > 0 && (
          <div>
            <span className="label-mono">ATTENDEES</span>
            <div className="mt-2 space-y-1">
              {event.attendees.map((a) => (
                <div key={a.email} className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-ink-600 flex items-center justify-center font-mono text-[10px] text-white">
                    {(a.name || a.email).slice(0, 2).toUpperCase()}
                  </span>
                  <span className="font-mono text-xs text-silver-axo">
                    {a.name || a.email}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {event.meet_link && (
          <a
            href={event.meet_link}
            target="_blank"
            rel="noreferrer"
            className="btn-ghost text-xs inline-flex"
          >
            <ExternalLink size={13} className="mr-1" /> Join Google Meet
          </a>
        )}

        <div>
          <span className="label-mono">AGENT PREP</span>
          {prep ? (
            <ul className="mt-2 space-y-1.5">
              {prep.map((b, i) => (
                <li
                  key={i}
                  className="panel-inset p-2 font-mono text-xs text-white"
                >
                  • {b}
                </li>
              ))}
            </ul>
          ) : (
            <button
              onClick={genPrep}
              disabled={busy}
              className="btn-primary text-xs mt-2"
            >
              {busy ? "Preparing…" : "Prepare with agent"}
            </button>
          )}
        </div>

        <div className="flex gap-2 pt-2 border-t border-ink-700/50">
          <button onClick={del} className="btn-danger text-xs">
            Delete
          </button>
        </div>
      </div>
    </SlideOver>
  );
}

function ScheduleMeetingForm({ onDone }: { onDone: () => void }) {
  const [withEmail, setWithEmail] = useState("");
  const [purpose, setPurpose] = useState("");
  const [duration, setDuration] = useState(30);
  const [slots, setSlots] = useState<FreeSlot[] | null>(null);
  const [picked, setPicked] = useState<FreeSlot | null>(null);
  const [busy, setBusy] = useState(false);

  const findSlots = async () => {
    setBusy(true);
    try {
      const out: FreeSlot[] = [];
      for (let i = 1; i <= 5 && out.length < 3; i++) {
        const d = new Date();
        d.setDate(d.getDate() + i);
        if (d.getDay() === 0 || d.getDay() === 6) continue;
        const free = await calendarApi.getFreeSlots(
          d.toISOString().slice(0, 10),
          duration
        );
        out.push(...free.slice(0, 2));
      }
      setSlots(out.slice(0, 3));
    } finally {
      setBusy(false);
    }
  };

  const book = async () => {
    if (!picked) return;
    setBusy(true);
    try {
      await calendarApi.createEvent({
        summary: purpose || "Meeting",
        start: picked.start,
        end: picked.end,
        attendees: withEmail ? [withEmail] : [],
        meet_link: true,
      });
      pushToast("Event created and invite sent.", "success");
      onDone();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="label-mono block mb-1">With (email)</label>
        <input
          className="input w-full"
          value={withEmail}
          onChange={(e) => setWithEmail(e.target.value)}
          placeholder="person@example.com"
        />
      </div>
      <div>
        <label className="label-mono block mb-1">Purpose</label>
        <input
          className="input w-full"
          value={purpose}
          onChange={(e) => setPurpose(e.target.value)}
          placeholder="What's the meeting about?"
        />
      </div>
      <div>
        <label className="label-mono block mb-1">Duration</label>
        <select
          className="input w-full"
          value={duration}
          onChange={(e) => setDuration(Number(e.target.value))}
        >
          <option value={15}>15 min</option>
          <option value={30}>30 min</option>
          <option value={60}>60 min</option>
        </select>
      </div>
      <button
        onClick={findSlots}
        disabled={busy}
        className="btn-ghost text-xs w-full"
      >
        {busy ? "Finding…" : "Find slots"}
      </button>

      {slots && (
        <div className="space-y-2">
          {slots.length === 0 && (
            <p className="font-mono text-xs text-silver-axo">
              No open slots in the next 5 business days.
            </p>
          )}
          {slots.map((s) => {
            const d = parse(s.start);
            return (
              <button
                key={s.start}
                onClick={() => setPicked(s)}
                className={`w-full text-left panel-inset p-3 font-mono text-xs transition ${
                  picked?.start === s.start
                    ? "border-cyan-axo/50 text-cyan-axo"
                    : "text-silver-axo hover:text-white"
                }`}
              >
                {d?.toLocaleString([], {
                  weekday: "short",
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </button>
            );
          })}
          <button
            onClick={book}
            disabled={!picked || busy}
            className="btn-primary text-xs w-full"
          >
            Book it
          </button>
        </div>
      )}
    </div>
  );
}
