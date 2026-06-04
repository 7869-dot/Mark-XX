/** Jarvis's opening briefing, rendered as the mockup's briefing card: a
 *  greeting, a numbered "here's your situation" list (the real action items),
 *  and a one-line summary of what the sub-agents surfaced. */
export function BriefingCard({
  greeting,
  items,
  webCount,
  urgentCount,
  focusPrompt,
}: {
  greeting: string;
  items: string[];
  webCount: number;
  urgentCount: number;
  focusPrompt: string;
}) {
  const situation = items.filter(Boolean);

  return (
    <div className="axo-card">
      <div className="axo-greeting">{greeting}</div>
      {situation.length > 0 && <div className="axo-subtle">Here's your situation:</div>}

      {situation.length > 0 && (
        <div className="axo-situation">
          {situation.map((t, i) => (
            <div className="axo-sit-row" key={i}>
              <span className={`axo-sit-num ${i < 2 ? "hot" : "warm"}`}>
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="axo-sit-text">{t}</span>
            </div>
          ))}
        </div>
      )}

      <div className="axo-card-footer">
        {webCount > 0 && (
          <>
            Web agent pulled{" "}
            <span className="axo-hl-blue">
              {webCount} finding{webCount === 1 ? "" : "s"}
            </span>
            .{" "}
          </>
        )}
        {urgentCount > 0 && (
          <>
            Email agent flagged{" "}
            <span className="axo-hl-red">{urgentCount} urgent</span>{" "}
            thread{urgentCount === 1 ? "" : "s"} waiting.{" "}
          </>
        )}
        {focusPrompt || "What do you want to tackle first?"}
      </div>
    </div>
  );
}
