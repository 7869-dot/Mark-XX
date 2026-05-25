/** Minimal, dependency-free markdown renderer for agent replies.
 *
 * Handles the subset that actually shows up in chat: paragraphs, line breaks,
 * fenced code blocks, inline code, bold, italic, links, h2/h3 headers, and
 * unordered lists. Inputs are user-trusted (this is the user's own agent
 * replying to them) but we still escape HTML so a stray `<script>` in user
 * text doesn't execute. Full markdown libs (~50KB) aren't worth pulling in
 * for this surface. */
import { Fragment, type ReactNode } from "react";

function escape(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/** Inline transforms: **bold**, *italic*, `code`, [text](url). Returns React
 * nodes so we can render links safely without dangerouslySetInnerHTML on
 * untrusted hrefs. */
function renderInline(text: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = [];
  // Tokenize on inline markers. Order matters: code first so its contents
  // aren't re-interpreted as bold/italic.
  const re = /`([^`]+)`|\*\*([^*]+)\*\*|\*([^*]+)\*|\[([^\]]+)\]\(([^)\s]+)\)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) {
      out.push(<Fragment key={`${keyBase}-t${i++}`}>{text.slice(last, m.index)}</Fragment>);
    }
    if (m[1] !== undefined) {
      out.push(
        <code
          key={`${keyBase}-c${i++}`}
          className="px-1 py-0.5 rounded text-[0.9em]"
          style={{
            background: "var(--bg-tertiary)",
            border: "1px solid var(--border)",
            fontFamily: "var(--font-data)",
          }}
        >
          {m[1]}
        </code>
      );
    } else if (m[2] !== undefined) {
      out.push(<strong key={`${keyBase}-b${i++}`}>{m[2]}</strong>);
    } else if (m[3] !== undefined) {
      out.push(<em key={`${keyBase}-i${i++}`}>{m[3]}</em>);
    } else if (m[4] !== undefined && m[5] !== undefined) {
      // Only allow http(s) and mailto: links — refuse javascript: and others.
      const href = /^(https?:|mailto:)/i.test(m[5]) ? m[5] : "#";
      out.push(
        <a
          key={`${keyBase}-l${i++}`}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: "var(--accent-primary)", textDecoration: "underline" }}
        >
          {m[4]}
        </a>
      );
    }
    last = re.lastIndex;
  }
  if (last < text.length) {
    out.push(<Fragment key={`${keyBase}-t${i++}`}>{text.slice(last)}</Fragment>);
  }
  return out;
}

type Block =
  | { kind: "p"; text: string }
  | { kind: "h2" | "h3"; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "code"; lang: string; text: string };

function parse(src: string): Block[] {
  const lines = src.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    // Fenced code block
    if (line.startsWith("```")) {
      const lang = line.slice(3).trim();
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        buf.push(lines[i]);
        i++;
      }
      i++; // consume closing fence
      blocks.push({ kind: "code", lang, text: buf.join("\n") });
      continue;
    }
    if (line.startsWith("### ")) {
      blocks.push({ kind: "h3", text: line.slice(4).trim() });
      i++;
      continue;
    }
    if (line.startsWith("## ")) {
      blocks.push({ kind: "h2", text: line.slice(3).trim() });
      i++;
      continue;
    }
    // Bulleted list
    if (/^[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^[-*]\s+/, ""));
        i++;
      }
      blocks.push({ kind: "ul", items });
      continue;
    }
    // Numbered list
    if (/^\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\.\s+/, ""));
        i++;
      }
      blocks.push({ kind: "ol", items });
      continue;
    }
    // Blank line — skip
    if (line.trim() === "") {
      i++;
      continue;
    }
    // Paragraph: consume until blank, list marker, or fence
    const buf: string[] = [line];
    i++;
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !lines[i].startsWith("```") &&
      !/^[-*]\s+/.test(lines[i]) &&
      !/^\d+\.\s+/.test(lines[i]) &&
      !lines[i].startsWith("## ") &&
      !lines[i].startsWith("### ")
    ) {
      buf.push(lines[i]);
      i++;
    }
    blocks.push({ kind: "p", text: buf.join(" ") });
  }
  return blocks;
}

export function Markdown({ source }: { source: string }) {
  const blocks = parse(source);
  return (
    <div className="leading-relaxed space-y-2">
      {blocks.map((b, idx) => {
        const k = `b${idx}`;
        if (b.kind === "h2")
          return (
            <h2
              key={k}
              className="text-lg mt-1 mb-1"
              style={{ fontFamily: "var(--font-display)" }}
            >
              {renderInline(b.text, k)}
            </h2>
          );
        if (b.kind === "h3")
          return (
            <h3
              key={k}
              className="text-base mt-1 mb-0.5"
              style={{ fontFamily: "var(--font-display)" }}
            >
              {renderInline(b.text, k)}
            </h3>
          );
        if (b.kind === "ul")
          return (
            <ul key={k} className="list-disc pl-5 space-y-0.5">
              {b.items.map((it, j) => (
                <li key={j}>{renderInline(it, `${k}-${j}`)}</li>
              ))}
            </ul>
          );
        if (b.kind === "ol")
          return (
            <ol key={k} className="list-decimal pl-5 space-y-0.5">
              {b.items.map((it, j) => (
                <li key={j}>{renderInline(it, `${k}-${j}`)}</li>
              ))}
            </ol>
          );
        if (b.kind === "code")
          return (
            <pre
              key={k}
              className="overflow-x-auto p-3 text-[12.5px] leading-snug"
              style={{
                background: "var(--bg-tertiary)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                fontFamily: "var(--font-data)",
              }}
            >
              <code>{escape(b.text)}</code>
            </pre>
          );
        return (
          <p key={k} className="whitespace-pre-wrap break-words">
            {renderInline(b.text, k)}
          </p>
        );
      })}
    </div>
  );
}
