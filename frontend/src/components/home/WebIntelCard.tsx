import type { WebFind } from "@/lib/api";

function hostname(u: string): string {
  try {
    return new URL(u).hostname.replace(/^www\./, "");
  } catch {
    return u;
  }
}

export function WebIntelCard({ find }: { find: WebFind }) {
  const host = hostname(find.url);
  const score = Math.max(0, Math.min(1, Number(find.relevance_score) || 0));

  return (
    <a className="axo-web-item" href={find.url} target="_blank" rel="noopener noreferrer">
      <div className="axo-web-top">
        <img
          className="axo-favicon"
          src={`https://www.google.com/s2/favicons?domain=${host}&sz=32`}
          alt=""
          width={16}
          height={16}
          loading="lazy"
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.visibility = "hidden";
          }}
        />
        <span className="axo-web-domain">{host}</span>
        {find.category && <span className="axo-web-cat">{find.category}</span>}
      </div>
      <div className="axo-web-title">{find.title}</div>
      <div className="axo-web-snippet">{find.summary}</div>
      <div className="axo-rel-wrap">
        <div className="axo-rel-bg">
          <div className="axo-rel-fill" style={{ width: `${Math.round(score * 100)}%` }} />
        </div>
        <span className="axo-rel-pct">{Math.round(score * 100)}%</span>
      </div>
    </a>
  );
}
