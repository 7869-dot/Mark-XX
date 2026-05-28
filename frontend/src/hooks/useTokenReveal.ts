import { useCallback, useEffect, useRef, useState } from "react";

/** Reveals an already-received string token-by-token, so an agent reply appears
 * to form in real time with a trailing cursor.
 *
 * This is deliberately a *client-side reveal*, not a network stream: the chat
 * API returns the full reply in one response, and pretending otherwise would be
 * dishonest. When the backend grows SSE/streaming, swap `start()` for feeding
 * chunks into `setText` directly and the UI stays identical.
 *
 * Respects prefers-reduced-motion (and very long messages) by snapping to full
 * text instead of animating. */
const CHARS_PER_TICK = 3;
const TICK_MS = 16;
const MAX_ANIMATED_CHARS = 1200; // snap anything longer to avoid a slow crawl

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
}

export function useTokenReveal() {
  const [activeId, setActiveId] = useState<string | null>(null);
  const [text, setText] = useState("");
  const fullRef = useRef("");
  const idxRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const finish = useCallback(() => {
    stop();
    setActiveId(null);
    setText("");
  }, [stop]);

  const start = useCallback(
    (id: string, full: string) => {
      stop();
      if (prefersReducedMotion() || full.length > MAX_ANIMATED_CHARS) {
        // Nothing to animate — caller renders the full row immediately.
        setActiveId(null);
        setText("");
        return;
      }
      fullRef.current = full;
      idxRef.current = 0;
      setActiveId(id);
      setText("");
      timerRef.current = setInterval(() => {
        idxRef.current = Math.min(
          idxRef.current + CHARS_PER_TICK,
          fullRef.current.length
        );
        setText(fullRef.current.slice(0, idxRef.current));
        if (idxRef.current >= fullRef.current.length) {
          stop();
          setActiveId(null); // hand rendering back to the committed row
        }
      }, TICK_MS);
    },
    [stop]
  );

  useEffect(() => stop, [stop]);

  return { activeId, text, start, finish };
}
