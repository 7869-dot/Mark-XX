import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { IconArrowRight, IconCheck, IconSparkles } from "@tabler/icons-react";
import { api, type OnboardingQuestion } from "@/lib/api";
import { pushToast } from "@/lib/toast";

/** First-interaction onboarding (Section 2). Walks the user through Jarvis's 5
 * questions one at a time — option-select buttons for the first three, free text
 * for the last two — then writes the answers to the memory profile. */
export function OnboardingCard({
  greeting,
  questions,
  onComplete,
}: {
  greeting: string;
  questions: OnboardingQuestion[];
  onComplete: () => void;
}) {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});
  const [submitting, setSubmitting] = useState(false);

  const q = questions[step];
  const last = step === questions.length - 1;
  const isMulti = q.type === "options" && q.multi;

  const value = answers[q.id];
  const canAdvance =
    q.type === "options"
      ? isMulti
        ? Array.isArray(value) && value.length > 0
        : !!value
      : typeof value === "string" && value.trim().length > 0;

  const setAnswer = (v: string | string[]) =>
    setAnswers((a) => ({ ...a, [q.id]: v }));

  const toggleMulti = (opt: string) => {
    const cur = Array.isArray(value) ? value : [];
    setAnswer(cur.includes(opt) ? cur.filter((x) => x !== opt) : [...cur, opt]);
  };

  const next = async (auto?: string) => {
    if (auto !== undefined) setAnswer(auto);
    if (!last) {
      setStep((s) => s + 1);
      return;
    }
    // Final step — persist.
    setSubmitting(true);
    try {
      const payload = { ...answers, ...(auto !== undefined ? { [q.id]: auto } : {}) };
      await api.submitOnboarding(payload);
      pushToast("Jarvis is set up — let's go.", "success");
      onComplete();
    } catch {
      pushToast("Couldn't save that — try again?", undefined);
      setSubmitting(false);
    }
  };

  return (
    <div className="h-full flex items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="w-full max-w-lg rounded-2xl p-6"
        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}
      >
        <div className="flex items-center gap-2 mb-3" style={{ color: "var(--accent-primary)" }}>
          <IconSparkles size={18} />
          <span className="text-xs tracking-wide" style={{ fontFamily: "var(--font-data)" }}>
            JARVIS · SETUP
          </span>
        </div>
        <p className="text-sm mb-5 leading-relaxed" style={{ color: "var(--text-secondary)" }}>
          {greeting}
        </p>

        {/* Progress dots */}
        <div className="flex gap-1.5 mb-5">
          {questions.map((_, i) => (
            <span
              key={i}
              className="h-1 flex-1 rounded-full transition-colors"
              style={{ background: i <= step ? "var(--accent-primary)" : "var(--border)" }}
            />
          ))}
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={q.id}
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -16 }}
            transition={{ duration: 0.25 }}
          >
            <h2 className="text-lg mb-4" style={{ fontFamily: "var(--font-display)", color: "var(--text-primary)" }}>
              {q.question}
            </h2>

            {q.type === "options" ? (
              <div className="grid gap-2">
                {(q.options || []).map((opt) => {
                  const selected = isMulti
                    ? Array.isArray(value) && value.includes(opt)
                    : value === opt;
                  return (
                    <motion.button
                      key={opt}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => (isMulti ? toggleMulti(opt) : next(opt))}
                      className="text-left px-4 py-2.5 rounded-xl text-sm transition flex items-center justify-between"
                      style={{
                        border: `1px solid ${selected ? "var(--accent-primary)" : "var(--border)"}`,
                        background: selected ? "var(--accent-blue-muted, rgba(93,202,165,0.12))" : "transparent",
                        color: selected ? "var(--accent-primary)" : "var(--text-primary)",
                      }}
                    >
                      {opt}
                      {selected && <IconCheck size={15} />}
                    </motion.button>
                  );
                })}
              </div>
            ) : (
              <textarea
                autoFocus
                value={(value as string) || ""}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Type your answer…"
                rows={3}
                className="input w-full text-sm resize-none"
              />
            )}
          </motion.div>
        </AnimatePresence>

        {/* Continue / Finish — shown for multi-select + text steps */}
        {(isMulti || q.type === "text") && (
          <button
            onClick={() => next()}
            disabled={!canAdvance || submitting}
            className="btn-primary mt-5 w-full inline-flex items-center justify-center gap-1.5 py-2.5"
            style={{ opacity: !canAdvance || submitting ? 0.5 : 1 }}
          >
            {submitting ? "Saving…" : last ? "Finish setup" : "Continue"}
            {!submitting && <IconArrowRight size={16} />}
          </button>
        )}
      </motion.div>
    </div>
  );
}
