import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { IconMail, IconSparkles, IconChevronRight } from "@tabler/icons-react";
import { api, type JarvisContext, type JarvisAgentTask } from "@/lib/api";
import { staggerContainer, slideInLeft, slideUp, fadeUp, pulse } from "@/lib/animations";

const PRIORITY_STYLE: Record<string, { bg: string; color: string }> = {
  now: { bg: "rgba(216,90,48,0.14)", color: "var(--accent-coral, #D85A30)" },
  today: { bg: "rgba(239,159,39,0.14)", color: "var(--accent-gold, #EF9F27)" },
  this_week: { bg: "rgba(127,119,221,0.14)", color: "var(--accent-secondary, #7F77DD)" },
};

export function JarvisPanel() {
  const navigate = useNavigate();
  const [ctx, setCtx] = useState<JarvisContext | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    api
      .jarvisContext()
      .then((r) => {
        if (r.context) {
          setCtx(r.context);
          setState("ready");
        } else {
          setState("error"); // graceful — Jarvis is thinking
        }
      })
      .catch(() => setState("error"));
  }, []);

  if (state === "loading") {
    return (
      <section className="panel p-6">
        <div className="space-y-3">
          <div className="skeleton h-6 w-3/4" />
          <div className="skeleton h-4 w-1/2" />
          <div className="skeleton h-4 w-2/3" />
          <div className="skeleton h-16 w-full mt-4" />
        </div>
      </section>
    );
  }

  if (state === "error" || !ctx) {
    return (
      <section className="panel p-6">
        <div className="flex items-center gap-2" style={{ color: "var(--text-secondary)" }}>
          <JarvisMark />
          <span className="text-sm" style={{ fontFamily: "var(--font-body)" }}>
            Jarvis is thinking…
          </span>
        </div>
      </section>
    );
  }

  return (
    <motion.section
      className="panel p-6"
      initial="hidden"
      animate="visible"
      variants={staggerContainer}
    >
      {/* Section A — Greeting */}
      <motion.div variants={fadeUp} className="flex items-start gap-3 mb-5">
        <JarvisMark />
        <p
          className="text-lg leading-snug"
          style={{ color: "var(--text-primary)", fontFamily: "var(--font-display)", fontWeight: 600 }}
        >
          {ctx.greeting}
        </p>
      </motion.div>

      {/* Section B — What Jarvis knows */}
      {ctx.known_about_user.length > 0 && (
        <div className="mb-5">
          <div className="label-mono mb-2">What I know right now</div>
          <motion.ul variants={staggerContainer} className="space-y-1.5">
            {ctx.known_about_user.map((item, i) => (
              <motion.li
                key={i}
                variants={slideInLeft}
                className="text-[13px] flex items-start gap-2"
                style={{ color: "var(--text-secondary)", fontFamily: "var(--font-body)" }}
              >
                <span style={{ color: "var(--text-muted)" }}>—</span>
                <span>{item}</span>
              </motion.li>
            ))}
          </motion.ul>
        </div>
      )}

      {/* Section C — The Question */}
      {!dismissed && ctx.question && (
        <motion.div
          variants={fadeUp}
          className="mb-5 rounded-lg p-4"
          style={{ background: "var(--bg-elevated)", borderLeft: "2px solid var(--accent-primary)" }}
        >
          <motion.p
            variants={pulse}
            animate="animate"
            className="text-[15px] mb-3"
            style={{ color: "var(--text-primary)", fontFamily: "var(--font-body)", fontWeight: 500, transformOrigin: "left" }}
          >
            {ctx.question}
          </motion.p>
          <div className="flex gap-2">
            <button
              onClick={() => navigate(`/jarvis?q=${encodeURIComponent(ctx.question)}`)}
              className="btn-primary text-xs py-1.5 px-3"
            >
              Let's get into it
            </button>
            <button
              onClick={() => setDismissed(true)}
              className="text-xs py-1.5 px-3 rounded"
              style={{ border: "1px solid var(--border)", color: "var(--text-secondary)" }}
            >
              Not now
            </button>
          </div>
        </motion.div>
      )}

      {/* Section D — Team briefing */}
      {ctx.team_briefing.length > 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
        >
          <div className="label-mono mb-2">I've briefed the team</div>
          <motion.div variants={staggerContainer} initial="hidden" animate="visible" className="space-y-2">
            {ctx.team_briefing.map((task, i) => (
              <TaskCard key={i} task={task} />
            ))}
          </motion.div>
        </motion.div>
      )}
    </motion.section>
  );
}

function TaskCard({ task }: { task: JarvisAgentTask }) {
  const [open, setOpen] = useState(false);
  const pr = PRIORITY_STYLE[task.priority] || PRIORITY_STYLE.today;
  return (
    <motion.div
      variants={slideUp}
      onClick={() => setOpen((o) => !o)}
      className="rounded-lg p-3 cursor-pointer"
      style={{ background: "var(--bg-elevated)" }}
    >
      <div className="flex items-center gap-2.5">
        <span style={{ color: "var(--accent-primary)" }}>
          {task.agent_role === "email" ? <IconMail size={15} /> : <IconSparkles size={15} />}
        </span>
        <span
          className="flex-1 text-[13px] truncate"
          style={{ color: "var(--text-primary)", fontFamily: "var(--font-body)" }}
        >
          {open ? task.task_description : task.task_description.slice(0, 48) + (task.task_description.length > 48 ? "…" : "")}
        </span>
        <span
          className="text-[9px] px-1.5 py-0.5 rounded uppercase tracking-wider shrink-0"
          style={{ background: pr.bg, color: pr.color, fontFamily: "var(--font-data)" }}
        >
          {task.priority.replace("_", " ")}
        </span>
        <motion.span animate={{ rotate: open ? 90 : 0 }} style={{ color: "var(--text-muted)" }}>
          <IconChevronRight size={14} />
        </motion.span>
      </div>
    </motion.div>
  );
}

/** Abstract, faceless Jarvis mark. */
function JarvisMark() {
  return (
    <span
      className="inline-flex items-center justify-center shrink-0 rounded-full"
      style={{
        width: 28,
        height: 28,
        background: "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary, #7F77DD))",
      }}
    >
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#080A0F" }} />
    </span>
  );
}
