import type { JarvisSession } from "@/lib/api";

type Briefing = Extract<JarvisSession, { onboarding: false }>;

/**
 * Render the morning briefing as Jarvis's opening message — a real PA voice,
 * not a dashboard widget. Built from the briefing API response (action items,
 * email counts, web finds). Empty sections are skipped naturally.
 */
export function buildGreeting(
  session: Briefing,
  userName: string,
  draftsCount: number
): string {
  const hr = new Date().getHours();
  const part = hr < 12 ? "Good morning" : hr < 18 ? "Good afternoon" : "Good evening";
  const name = (userName || "").trim().split(" ")[0];

  const lines: string[] = [];
  lines.push(`${part}${name ? `, ${name}` : ""}. Here's where things stand:`);

  // Tasks first.
  const tasks = (session.action_items || []).filter(Boolean);
  if (tasks.length) {
    lines.push("");
    lines.push(
      `You have ${tasks.length} thing${tasks.length === 1 ? "" : "s"} that need attention today:`
    );
    tasks.forEach((t) => lines.push(`- ${t}`));
  }

  // Then urgent emails + drafted replies.
  const urgent = Number(session.reports?.email?.counts?.urgent ?? 0);
  if (urgent || draftsCount) {
    lines.push("");
    const bits: string[] = [];
    if (urgent) bits.push(`flagged ${urgent} urgent message${urgent === 1 ? "" : "s"}`);
    if (draftsCount)
      bits.push(`drafted ${draftsCount} repl${draftsCount === 1 ? "y" : "ies"} for you`);
    lines.push(`On the email front, I've ${bits.join(" and ")} — check the **Emails** tab.`);
  }

  // Then web intel.
  const finds = session.reports?.web?.top_finds || [];
  if (finds.length) {
    lines.push("");
    const top = finds[0];
    const more = finds.length > 1 ? ` (plus ${finds.length - 1} more in **Web Intel**)` : "";
    lines.push(`In the news: ${top.summary || top.title}${more}.`);
  }

  lines.push("");
  lines.push(session.focus_prompt || "What do you want to start with?");
  return lines.join("\n");
}
