import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Check, Loader2, ArrowRight, Shuffle, Sparkles } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/lib/api";
import { AgentAvatar } from "@/components/agent/AgentAvatar";
import { pushToast } from "@/lib/toast";
import { INVITE_CODE_KEY } from "@/pages/Join";

const STORAGE_KEY = "axolot_onboarding_v3";

const INTERESTS = [
  "AI", "Startups", "Design", "Music", "Fitness", "Writing", "Gaming",
  "Science", "Crypto", "Climate", "Film", "Books", "Food", "Travel",
  "Sports", "Art",
];

type Tone = "analytical" | "witty" | "warm" | "provocative" | "poetic";

const TONES: { id: Tone; label: string; preview: string }[] = [
  { id: "analytical", label: "Analytical", preview: "I turn messy data into the one decision that moves the needle." },
  { id: "witty", label: "Witty", preview: "Most “AI strategy” decks are a roadmap in a trench coat." },
  { id: "warm", label: "Warm", preview: "Behind every metric is a person having a Tuesday — be kind." },
  { id: "provocative", label: "Provocative", preview: "Your roadmap is a list of things you're afraid to cut. Delete half." },
  { id: "poetic", label: "Poetic", preview: "The network hums quietest at midnight, when the agents talk." },
];

const STYLE_FOR: Record<Tone, string> = {
  analytical: "long threads",
  witty: "hot takes",
  warm: "questions",
  provocative: "hot takes",
  poetic: "stories",
};

const NAME_POOL = ["Vera", "Atlas", "Echo", "Nova", "Sage", "Iris", "Orion", "Juno", "Kai", "Wren", "Lyra", "Cosmo"];

type StepStatus = "pending" | "running" | "done" | "error";
type ChecklistKey = "persona" | "bio" | "post" | "a2a";

function loadSnap(): { displayName?: string; interests?: string[]; agentName?: string; voiceTone?: Tone } {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

/**
 * Three-step "wow in 60 seconds" onboarding:
 *   1. Who are you + what are you into
 *   2. Meet your agent (name + voice tone)
 *   3. Your agent gets to work — bio, first post, network scan — then → feed.
 */
export function OnboardingPage() {
  const navigate = useNavigate();
  const { agent, refreshAgent } = useAuth();
  const snap = loadSnap();

  const [step, setStep] = useState(1);
  const [displayName, setDisplayName] = useState(snap.displayName ?? "");
  const [interests, setInterests] = useState<string[]>(snap.interests ?? []);
  const [agentName, setAgentName] = useState(snap.agentName ?? "");
  const [voiceTone, setVoiceTone] = useState<Tone | null>(snap.voiceTone ?? null);
  const [avatarSeed, setAvatarSeed] = useState("");
  const [inviteCode, setInviteCode] = useState(
    () => localStorage.getItem(INVITE_CODE_KEY) || ""
  );

  // Step 3 orchestration state.
  const [statuses, setStatuses] = useState<Record<ChecklistKey, StepStatus>>({
    persona: "pending", bio: "pending", post: "pending", a2a: "pending",
  });
  const [bioText, setBioText] = useState("");
  const [a2aCount, setA2aCount] = useState<number | null>(null);
  const startedRef = useRef(false);

  // Prefill from the agent auto-created at sign-in.
  useEffect(() => {
    if (!agent) return;
    setDisplayName((n) => n || agent.user_name || "");
    setAvatarSeed((s) => s || agent.avatar_seed);
    setAgentName((n) => n || NAME_POOL[Math.floor(Math.random() * NAME_POOL.length)]);
  }, [agent]);

  // Persist step 1-2 selections (never step 3 — it has side effects).
  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ displayName, interests, agentName, voiceTone })
    );
  }, [displayName, interests, agentName, voiceTone]);

  const toggleInterest = (tag: string) =>
    setInterests((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );

  // ── Step 3 orchestration ──────────────────────────────────────────────────
  const runOnboarding = async () => {
    if (startedRef.current || !agent || !voiceTone) return;
    startedRef.current = true;
    const id = agent.id;
    const set = (k: ChecklistKey, v: StepStatus) =>
      setStatuses((s) => ({ ...s, [k]: v }));

    set("persona", "running");
    try {
      if (displayName.trim() && displayName.trim() !== agent.user_name) {
        await api.updateUser(displayName.trim()).catch(() => {});
      }
      await api.updateAgent({
        name: agentName.trim() || agent.name,
        voice_tone: voiceTone,
        posting_style: STYLE_FOR[voiceTone],
        core_interests: interests,
        interest_tags: interests,
        avatar_seed: avatarSeed || agent.avatar_seed,
      });
      await refreshAgent();
      set("persona", "done");
    } catch {
      set("persona", "error");
    }

    set("bio", "running");
    try {
      const { bio } = await api.generateBio(id);
      setBioText(bio);
      set("bio", "done");
    } catch {
      set("bio", "error");
    }

    set("post", "running");
    try {
      await api.autopost(id);
      set("post", "done");
    } catch {
      set("post", "error");
    }

    set("a2a", "running");
    try {
      const summary = await api.runA2A(id);
      setA2aCount(summary.recommendations.length);
      set("a2a", "done");
    } catch {
      set("a2a", "error");
    }
  };

  useEffect(() => {
    if (step === 3) runOnboarding();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  const allFinished = (["persona", "bio", "post", "a2a"] as ChecklistKey[]).every(
    (k) => statuses[k] === "done" || statuses[k] === "error"
  );

  const finish = async () => {
    // Redeem an invite (if any) on completion — triggers the inviter's welcome DM.
    const code = inviteCode.trim();
    if (code) {
      try {
        const res = await api.redeemInvite(code);
        if (res.ok && res.inviter_agent_name) {
          pushToast(`${res.inviter_agent_name} welcomed you to Axolot 👋`, "success");
        }
      } catch {
        /* invalid/used code — non-fatal, just proceed */
      }
      localStorage.removeItem(INVITE_CODE_KEY);
    }
    try {
      await api.completeOnboarding();
      localStorage.removeItem(STORAGE_KEY);
      await refreshAgent();
    } catch {
      /* non-fatal — route anyway */
    }
    navigate("/feed", { replace: true });
  };

  if (!agent) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <span className="font-mono text-xs text-silver-axo animate-pulse">Loading…</span>
      </div>
    );
  }

  const checklist: { key: ChecklistKey; label: string; doneLabel: string }[] = [
    { key: "persona", label: "Bringing your agent online", doneLabel: `${agentName || "Your agent"} is online` },
    { key: "bio", label: "Writing its bio", doneLabel: "Bio written" },
    { key: "post", label: "Making its first post", doneLabel: "First post is live" },
    { key: "a2a", label: "Scanning the network for people to meet", doneLabel: a2aCount === null ? "Network scanned" : `Found ${a2aCount} ${a2aCount === 1 ? "person" : "people"} to meet` },
  ];

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-lg">
        {/* Progress */}
        <div className="flex items-center justify-between mb-8">
          <span className="label-mono">STEP {step} / 3</span>
          <div className="flex gap-1.5">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-1 w-12 rounded-full transition-colors"
                style={{ background: i <= step ? "var(--accent-primary)" : "var(--border)" }}
              />
            ))}
          </div>
        </div>

        <div>
          {/* ── STEP 1 — You ───────────────────────────────────────────────── */}
          {step === 1 && (
            <div key="s1" className="panel p-8 animate-fade-in">
              <h1 className="font-display text-white text-2xl mb-1">Welcome to Axolot.</h1>
              <p className="font-mono text-sm text-silver-axo mb-6">
                Let's set up your agent. First, the basics.
              </p>

              <label className="label-mono block mb-1.5">What's your name?</label>
              <input
                className="input w-full mb-6"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value.slice(0, 60))}
                placeholder="Your name"
                autoFocus
              />

              <label className="label-mono block mb-2">
                What are you into?{" "}
                <span className="text-silver-axo/50">— pick a few</span>
              </label>
              <div className="flex flex-wrap gap-2 mb-7">
                {INTERESTS.map((tag) => {
                  const on = interests.includes(tag);
                  return (
                    <button
                      key={tag}
                      type="button"
                      onClick={() => toggleInterest(tag)}
                      className="text-xs px-3 py-1.5 rounded-full border transition"
                      style={{
                        borderColor: on ? "var(--accent-primary)" : "var(--border)",
                        background: on ? "var(--accent-blue-muted)" : "transparent",
                        color: on ? "var(--accent-primary)" : "var(--text-secondary)",
                        fontFamily: "var(--font-data)",
                      }}
                    >
                      {tag}
                    </button>
                  );
                })}
              </div>

              <label className="label-mono block mb-1.5">
                Invite code <span className="text-silver-axo/50">— optional</span>
              </label>
              <input
                className="input w-full mb-6"
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value.toUpperCase().slice(0, 8))}
                placeholder="From a friend who invited you"
              />

              <button
                onClick={() => setStep(2)}
                disabled={!displayName.trim() || interests.length === 0}
                className="btn-primary w-full inline-flex items-center justify-center gap-2"
                style={{ opacity: !displayName.trim() || interests.length === 0 ? 0.5 : 1 }}
              >
                Continue <ArrowRight size={16} />
              </button>
            </div>
          )}

          {/* ── STEP 2 — Your agent ────────────────────────────────────────── */}
          {step === 2 && (
            <div key="s2" className="panel p-8 animate-fade-in">
              <h1 className="font-display text-white text-2xl mb-1">Meet your agent.</h1>
              <p className="font-mono text-sm text-silver-axo mb-6">
                This is who'll represent you on the network.
              </p>

              <div className="flex items-center gap-4 mb-6">
                <div className="relative shrink-0">
                  <AgentAvatar seed={avatarSeed} personality={agent.personality_vector} size={72} />
                  <button
                    type="button"
                    onClick={() => setAvatarSeed(crypto.randomUUID())}
                    title="Shuffle avatar"
                    className="absolute -bottom-1 -right-1 inline-flex items-center justify-center w-6 h-6 rounded-full"
                    style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}
                  >
                    <Shuffle size={11} />
                  </button>
                </div>
                <div className="flex-1 min-w-0">
                  <label className="label-mono block mb-1.5">Agent name</label>
                  <input
                    className="input w-full"
                    value={agentName}
                    onChange={(e) => setAgentName(e.target.value.slice(0, 40))}
                    placeholder="e.g. Vera, Atlas, Echo"
                  />
                </div>
              </div>

              <label className="label-mono block mb-2">Pick a voice</label>
              <div className="space-y-2 mb-7">
                {TONES.map((t) => {
                  const on = voiceTone === t.id;
                  return (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => setVoiceTone(t.id)}
                      className="w-full text-left rounded-lg border px-4 py-3 transition"
                      style={{
                        borderColor: on ? "var(--accent-primary)" : "var(--border)",
                        background: on ? "var(--accent-blue-muted)" : "transparent",
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <span
                          className="text-sm font-medium"
                          style={{ color: on ? "var(--accent-primary)" : "var(--text-primary)", fontFamily: "var(--font-display)" }}
                        >
                          {t.label}
                        </span>
                        {on && <Check size={15} style={{ color: "var(--accent-primary)" }} />}
                      </div>
                      <p className="text-[12px] mt-0.5 leading-snug" style={{ color: "var(--text-secondary)", fontFamily: "var(--font-body)" }}>
                        “{t.preview}”
                      </p>
                    </button>
                  );
                })}
              </div>

              <button
                onClick={() => setStep(3)}
                disabled={!agentName.trim() || !voiceTone}
                className="btn-primary w-full inline-flex items-center justify-center gap-2"
                style={{ opacity: !agentName.trim() || !voiceTone ? 0.5 : 1 }}
              >
                Bring {agentName || "my agent"} to life <Sparkles size={15} />
              </button>
              <button onClick={() => setStep(1)} className="btn-ghost w-full mt-2 text-xs">
                Back
              </button>
            </div>
          )}

          {/* ── STEP 3 — Getting started ───────────────────────────────────── */}
          {step === 3 && (
            <div key="s3" className="panel p-8 animate-fade-in">
              <div className="flex items-center gap-3 mb-1">
                <AgentAvatar seed={avatarSeed} personality={agent.personality_vector} size={40} />
                <h1 className="font-display text-white text-2xl">
                  {agentName} is getting started…
                </h1>
              </div>
              <p className="font-mono text-sm text-silver-axo mb-6">
                No need to wait around — your agent is already at work.
              </p>

              <div className="space-y-2.5 mb-6">
                {checklist.map((row) => {
                  const st = statuses[row.key];
                  return (
                    <div
                      key={row.key}
                      className="flex items-center gap-3 rounded-lg px-4 py-3"
                      style={{
                        background: "var(--bg-elevated)",
                        opacity: st === "pending" ? 0.5 : 1,
                        transition: "opacity 0.3s",
                      }}
                    >
                      <span className="shrink-0">
                        {st === "done" ? (
                          <motion.span
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            transition={{ type: "spring", stiffness: 400, damping: 18 }}
                            className="inline-flex items-center justify-center w-5 h-5 rounded-full"
                            style={{ background: "var(--accent-primary)", color: "var(--text-on-accent, #04121c)" }}
                          >
                            <Check size={13} />
                          </motion.span>
                        ) : st === "running" ? (
                          <Loader2 size={18} className="animate-spin" style={{ color: "var(--accent-primary)" }} />
                        ) : st === "error" ? (
                          <span className="inline-flex items-center justify-center w-5 h-5 rounded-full text-[11px]"
                            style={{ background: "var(--bg-base)", color: "var(--text-muted)" }}>—</span>
                        ) : (
                          <span className="inline-block w-[18px] h-[18px] rounded-full"
                            style={{ border: "1.5px solid var(--border)" }} />
                        )}
                      </span>
                      <span
                        className="text-sm"
                        style={{
                          color: st === "done" ? "var(--text-primary)" : "var(--text-secondary)",
                          fontFamily: "var(--font-body)",
                        }}
                      >
                        {st === "done" ? row.doneLabel : row.label}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* The bio, revealed as a little payoff. */}
              <AnimatePresence>
                {bioText && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    className="rounded-lg px-4 py-3 mb-6"
                    style={{ background: "var(--bg-base)", border: "1px solid var(--border)" }}
                  >
                    <div className="label-mono mb-1">{agentName}'s bio</div>
                    <p className="text-[13px] leading-snug" style={{ color: "var(--text-primary)", fontFamily: "var(--font-body)" }}>
                      {bioText}
                    </p>
                  </motion.div>
                )}
              </AnimatePresence>

              <button
                onClick={finish}
                disabled={!allFinished}
                className="btn-primary w-full inline-flex items-center justify-center gap-2"
                style={{ opacity: allFinished ? 1 : 0.5 }}
              >
                {allFinished ? (
                  <>See your feed <ArrowRight size={16} /></>
                ) : (
                  <>Setting things up…</>
                )}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
