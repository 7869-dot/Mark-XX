import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/lib/api";
import { AgentAvatar } from "@/components/agent/AgentAvatar";

const GOAL_CATEGORIES = [
  "Career & Networking",
  "Freelance & Business",
  "Research & Learning",
  "Health & Habits",
  "Creative Projects",
  "Personal Finance",
];

const SLIDERS = [
  {
    key: "directness",
    label: "How do you prefer to communicate?",
    left: "Direct",
    right: "Diplomatic",
    invert: true,
  },
  {
    key: "risk_tolerance",
    label: "How do you approach new opportunities?",
    left: "Cautious",
    right: "Bold",
  },
  {
    key: "sociability",
    label: "How important is building relationships?",
    left: "Solo",
    right: "Highly social",
  },
  {
    key: "ambition",
    label: "How ambitious are your current goals?",
    left: "Steady",
    right: "Extremely ambitious",
  },
  {
    key: "openness",
    label: "How do you prefer to work?",
    left: "Deep focus",
    right: "Varied & exploratory",
  },
];

const STORAGE_KEY = "axolot_onboarding_step";

type OnboardingSnapshot = {
  step: number;
  agentName: string;
  chosenCategories: string[];
  biggestGoal: string;
  pv: Record<string, number>;
};

function loadSnapshot(): Partial<OnboardingSnapshot> {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

export function OnboardingPage() {
  const navigate = useNavigate();
  const { agent, refreshAgent } = useAuth();
  const snap = loadSnapshot();

  const [step, setStep] = useState(snap.step && snap.step >= 1 ? snap.step : 1);

  // Step 1 — agent name
  const [agentName, setAgentName] = useState(snap.agentName ?? "");

  // Step 2 — goals
  const [chosenCategories, setChosenCategories] = useState<string[]>(
    snap.chosenCategories ?? []
  );
  const [biggestGoal, setBiggestGoal] = useState(snap.biggestGoal ?? "");

  // Step 3 — personality
  const [pv, setPv] = useState<Record<string, number>>(
    snap.pv ?? {
      openness: 0.5,
      directness: 0.5,
      ambition: 0.5,
      sociability: 0.5,
      risk_tolerance: 0.5,
    }
  );

  // Step 4 — activation
  const [activating, setActivating] = useState(false);

  // Persist progress so a mid-onboarding refresh resumes exactly where it left off.
  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ step, agentName, chosenCategories, biggestGoal, pv })
    );
  }, [step, agentName, chosenCategories, biggestGoal, pv]);

  // Seed the agent-name field from the agent created at sign-in.
  useEffect(() => {
    if (agent) setAgentName((n) => n || agent.name);
  }, [agent]);

  const next = () => setStep((s) => s + 1);

  const finalize = async () => {
    setActivating(true);
    try {
      const goals = [
        ...chosenCategories.map((c) => `Focus on: ${c}`),
        ...(biggestGoal ? [biggestGoal] : []),
      ];
      await api.updateAgent({
        name: agentName,
        goals,
        personality_vector: pv,
        onboarded: { completed: true, step: 4 },
      });
      localStorage.removeItem(STORAGE_KEY);
      await refreshAgent();
      setTimeout(() => navigate("/dashboard"), 1200);
    } catch (e) {
      setActivating(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-2xl">
        <div className="flex items-center justify-between mb-8">
          <span className="label-mono">STEP {step + 1} / 5</span>
          <div className="flex gap-1">
            {[0, 1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className={`h-0.5 w-8 rounded-full ${
                  i <= step ? "bg-cyan-axo" : "bg-ink-600"
                }`}
              />
            ))}
          </div>
        </div>

        {/* STEP 1 — Name */}
        {step === 1 && (
          <div className="panel p-8 animate-fade-in">
            <h1 className="font-display text-white text-2xl mb-2">
              What should we call your agent?
            </h1>
            <p className="font-mono text-sm text-silver-axo mb-6">
              You can change this anytime.
            </p>
            <input
              className="input w-full mb-6"
              value={agentName}
              onChange={(e) => setAgentName(e.target.value)}
              placeholder="e.g. Echo, Atlas, Vera"
            />
            <button
              disabled={!agentName.trim()}
              onClick={next}
              className="btn-primary w-full"
            >
              Continue →
            </button>
          </div>
        )}

        {/* STEP 2 — Goals */}
        {step === 2 && (
          <div className="panel p-8 animate-fade-in">
            <h1 className="font-display text-white text-2xl mb-2">
              What do you want your agent to focus on?
            </h1>
            <p className="font-mono text-sm text-silver-axo mb-6">
              Pick all that apply. These will drive proactive behavior.
            </p>
            <div className="grid grid-cols-2 gap-2 mb-6">
              {GOAL_CATEGORIES.map((c) => {
                const on = chosenCategories.includes(c);
                return (
                  <button
                    key={c}
                    onClick={() =>
                      setChosenCategories((prev) =>
                        on ? prev.filter((x) => x !== c) : [...prev, c]
                      )
                    }
                    className={`text-left px-3 py-3 rounded-md border text-xs font-mono transition ${
                      on
                        ? "border-cyan-axo/50 bg-cyan-axo/10 text-cyan-axo"
                        : "border-ink-600 text-silver-axo hover:border-ink-500"
                    }`}
                  >
                    {c}
                  </button>
                );
              })}
            </div>
            <label className="label-mono block mb-2">
              Describe your biggest current goal in one sentence
            </label>
            <textarea
              className="input w-full mb-6 min-h-[80px] resize-none"
              value={biggestGoal}
              onChange={(e) => setBiggestGoal(e.target.value)}
            />
            <button
              onClick={next}
              className="btn-primary w-full"
              disabled={!chosenCategories.length && !biggestGoal.trim()}
            >
              Continue →
            </button>
          </div>
        )}

        {/* STEP 3 — Personality */}
        {step === 3 && (
          <div className="panel p-8 animate-fade-in">
            <h1 className="font-display text-white text-2xl mb-2">Calibrate your agent.</h1>
            <p className="font-mono text-sm text-silver-axo mb-6">
              These seed the initial personality. It will evolve as it learns you.
            </p>
            <div className="space-y-5">
              {SLIDERS.map((s) => {
                const val = pv[s.key] ?? 0.5;
                return (
                  <div key={s.key}>
                    <div className="font-display text-white text-sm mb-2">{s.label}</div>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.01}
                      value={val}
                      onChange={(e) =>
                        setPv({ ...pv, [s.key]: Number(e.target.value) })
                      }
                      className="w-full accent-cyan-axo"
                    />
                    <div className="flex justify-between text-[10px] font-mono text-silver-axo/70 mt-1">
                      <span>{s.left}</span>
                      <span>{s.right}</span>
                    </div>
                  </div>
                );
              })}
            </div>
            <button onClick={next} className="btn-primary w-full mt-8">
              Continue →
            </button>
          </div>
        )}

        {/* STEP 4 — Activation */}
        {step === 4 && (
          <div className="panel p-12 text-center animate-fade-in">
            <div className="flex justify-center mb-6 animate-bloom">
              <AgentAvatar
                seed={agent?.avatar_seed || agentName}
                personality={pv}
                size={140}
              />
            </div>
            <h1 className="font-display text-white text-3xl mb-3 tracking-tight">
              {agentName} is ready.
            </h1>
            {!activating ? (
              <>
                <p className="font-mono text-sm text-silver-axo mb-8 max-w-md mx-auto">
                  Your agent has a personality, a memory, and a purpose. It's already thinking about your goals.
                </p>
                <button onClick={finalize} className="btn-primary">
                  Enter the Command Center →
                </button>
              </>
            ) : (
              <p className="font-mono text-sm text-cyan-axo animate-pulse">
                Activating personality matrix…
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
