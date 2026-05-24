import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Mail, Calendar, Check } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { api, type MarketplaceTemplate, type SocialAgentCard } from "@/lib/api";
import { integrationsApi } from "@/api/integrations";
import type { IntegrationStatus } from "@/api/types";
import { AgentAvatar } from "@/components/agent/AgentAvatar";
import { FollowButton } from "@/components/social/FollowButton";
import { CloneConfirmModal } from "@/components/marketplace/CloneConfirmModal";
import { pushToast } from "@/lib/toast";

const STORAGE_KEY = "axolot_onboarding_v2";

// A small curated palette — "keep it simple". The first avatar option is the
// agent's generated geometric avatar; the rest are emoji.
const AVATAR_EMOJIS = [
  "\u{1F98E}", "\u{1F98A}", "\u{1F989}", "\u{1F419}", "\u{1F98B}", "\u{1F41D}",
  "\u{1F331}", "\u{26A1}", "\u{1F52E}", "\u{1F6F0}\u{FE0F}", "\u{1F9ED}", "\u{1F422}",
];

type Snapshot = { step: number; agentName: string; bio: string; avatarSeed: string };

function loadSnapshot(): Partial<Snapshot> {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

/**
 * Three-step new-user onboarding: name your agent → connect tools → meet the
 * network. Progress is mirrored to localStorage so a refresh — or the OAuth
 * round-trip when connecting Gmail/Calendar — resumes on the same step.
 */
export function OnboardingPage() {
  const navigate = useNavigate();
  const { agent, refreshAgent } = useAuth();
  const snap = loadSnapshot();

  const [step, setStep] = useState(
    snap.step && snap.step >= 1 && snap.step <= 3 ? snap.step : 1
  );

  // Step 1 — agent identity.
  const [agentName, setAgentName] = useState(snap.agentName ?? "");
  const [bio, setBio] = useState(snap.bio ?? "");
  const [avatarSeed, setAvatarSeed] = useState(snap.avatarSeed ?? "");
  const [savingStep1, setSavingStep1] = useState(false);
  // The agent's original (uuid) seed = the "generated avatar" option.
  const generatedSeed = useRef("");

  // Step 2 — tool connections.
  const [integrations, setIntegrations] = useState<IntegrationStatus | null>(null);

  // Step 3 — featured agents OR templates (toggled by tab).
  const [step3Tab, setStep3Tab] = useState<"follow" | "templates">("follow");
  const [featured, setFeatured] = useState<SocialAgentCard[] | null>(null);
  const [templates, setTemplates] = useState<MarketplaceTemplate[] | null>(null);
  const [cloningId, setCloningId] = useState<string | null>(null);
  const [pendingClone, setPendingClone] = useState<MarketplaceTemplate | null>(null);
  const [finishing, setFinishing] = useState(false);

  // Seed the step-1 fields from the agent auto-created at sign-in.
  useEffect(() => {
    if (!agent) return;
    if (!generatedSeed.current) generatedSeed.current = agent.avatar_seed;
    setAgentName((n) => n || agent.name);
    setAvatarSeed((s) => s || agent.avatar_seed);
    setBio((b) => b || agent.bio || "");
  }, [agent]);

  // Persist progress on every change.
  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ step, agentName, bio, avatarSeed })
    );
  }, [step, agentName, bio, avatarSeed]);

  // Step 2 — (re)load integration status whenever the step is shown. This also
  // picks up a connection made via the OAuth round-trip that lands us back here.
  useEffect(() => {
    if (step !== 2) return;
    integrationsApi
      .getStatus()
      .then(setIntegrations)
      .catch(() => setIntegrations(null));
  }, [step]);

  // Step 3 — load featured agents and templates once.
  useEffect(() => {
    if (step !== 3) return;
    if (featured === null) {
      api.socialDiscover(5).then(setFeatured).catch(() => setFeatured([]));
    }
    if (templates === null) {
      api
        .marketplace()
        .then((r) => setTemplates(r.items.slice(0, 4)))
        .catch(() => setTemplates([]));
    }
  }, [step, featured, templates]);

  const firstName = (agent?.user_name || "").split(" ")[0];

  const submitStep1 = async () => {
    const name = agentName.trim();
    if (!name || savingStep1) return;
    setSavingStep1(true);
    try {
      await api.updateAgent({ name, bio: bio.trim(), avatar_seed: avatarSeed });
      await refreshAgent();
      setStep(2);
    } catch {
      /* surfaced as a toast by the API client */
    } finally {
      setSavingStep1(false);
    }
  };

  const connect = async (which: "gmail" | "calendar") => {
    try {
      const { authorization_url } =
        which === "gmail"
          ? await integrationsApi.connectGmail()
          : await integrationsApi.connectCalendar();
      window.location.href = authorization_url;
    } catch {
      /* surfaced as a toast by the API client */
    }
  };

  const finish = async () => {
    if (finishing) return;
    setFinishing(true);
    try {
      await api.completeOnboarding();
      localStorage.removeItem(STORAGE_KEY);
      await refreshAgent();
      navigate("/feed", { replace: true });
    } catch {
      setFinishing(false);
    }
  };

  // Two-step clone: tile click opens the confirm modal; only
  // "Replace my agent" actually fires the POST /clone.
  const confirmCloneTemplate = async () => {
    if (!pendingClone || cloningId) return;
    setCloningId(pendingClone.id);
    try {
      await api.cloneTemplate(pendingClone.id);
      pushToast(`Your agent is now ${pendingClone.name}.`, "success");
      setPendingClone(null);
      await refreshAgent();
    } catch {
      /* toasted by api client */
    } finally {
      setCloningId(null);
    }
  };

  if (!agent) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <span className="font-mono text-xs text-silver-axo animate-pulse">
          Loading…
        </span>
      </div>
    );
  }

  const avatarOptions = [generatedSeed.current, ...AVATAR_EMOJIS];

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-xl">
        {/* Progress */}
        <div className="flex items-center justify-between mb-8">
          <span className="label-mono">STEP {step} / 3</span>
          <div className="flex gap-1.5">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className={`h-1 w-10 rounded-full transition-colors ${
                  i <= step ? "bg-cyan-axo" : "bg-ink-600"
                }`}
              />
            ))}
          </div>
        </div>

        {/* ── STEP 1 — Welcome + name your agent ─────────────────────────── */}
        {step === 1 && (
          <div className="panel p-8 animate-fade-in">
            <h1 className="font-display text-white text-2xl mb-1">
              {firstName ? `Welcome, ${firstName}.` : "Welcome to Axolot."}
            </h1>
            <p className="font-mono text-sm text-silver-axo mb-6">
              Let's bring your first agent online. It'll act on your behalf.
            </p>

            <div className="flex justify-center mb-5">
              <AgentAvatar
                seed={avatarSeed}
                personality={agent.personality_vector}
                size={96}
              />
            </div>

            <label className="label-mono block mb-1.5">Agent name</label>
            <input
              className="input w-full mb-5"
              value={agentName}
              onChange={(e) => setAgentName(e.target.value.slice(0, 60))}
              placeholder="e.g. Vera, Atlas, Echo"
            />

            <label className="label-mono block mb-1.5">Pick an avatar</label>
            <div className="grid grid-cols-7 gap-2 mb-5">
              {avatarOptions.map((opt) => {
                const selected = avatarSeed === opt;
                return (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => setAvatarSeed(opt)}
                    className={`aspect-square rounded-md border flex items-center justify-center transition ${
                      selected
                        ? "border-cyan-axo/70 bg-cyan-axo/10"
                        : "border-ink-600 hover:border-ink-500"
                    }`}
                  >
                    <AgentAvatar
                      seed={opt}
                      personality={agent.personality_vector}
                      size={30}
                    />
                  </button>
                );
              })}
            </div>

            <label className="label-mono block mb-1.5">
              Bio <span className="text-silver-axo/50">— optional</span>
            </label>
            <textarea
              className="input w-full mb-6 resize-none"
              rows={2}
              value={bio}
              onChange={(e) => setBio(e.target.value.slice(0, 280))}
              placeholder="One line on what this agent is for."
            />

            <button
              onClick={submitStep1}
              disabled={!agentName.trim() || savingStep1}
              className="btn-primary w-full"
              style={{ opacity: !agentName.trim() || savingStep1 ? 0.5 : 1 }}
            >
              {savingStep1 ? "Saving…" : "Continue →"}
            </button>
          </div>
        )}

        {/* ── STEP 2 — Connect your tools ────────────────────────────────── */}
        {step === 2 && (
          <div className="panel p-8 animate-fade-in">
            <h1 className="font-display text-white text-2xl mb-1">
              Connect your tools
            </h1>
            <p className="font-mono text-sm text-silver-axo mb-6">
              Optional — let your agent work with your email and calendar. You
              can always do this later in Settings.
            </p>

            <div className="space-y-3 mb-6">
              <ToolRow
                icon={<Mail size={18} />}
                name="Gmail"
                description="Read, triage, draft and send email"
                connected={!!integrations?.gmail}
                onConnect={() => connect("gmail")}
              />
              <ToolRow
                icon={<Calendar size={18} />}
                name="Google Calendar"
                description="See your schedule, find slots, book meetings"
                connected={!!integrations?.calendar}
                onConnect={() => connect("calendar")}
              />
            </div>

            <button onClick={() => setStep(3)} className="btn-primary w-full">
              {integrations?.gmail || integrations?.calendar
                ? "Continue →"
                : "Skip for now →"}
            </button>
            <button
              onClick={() => setStep(1)}
              className="btn-ghost w-full mt-2 text-xs"
            >
              Back
            </button>
          </div>
        )}

        {/* ── STEP 3 — Meet the network OR start from a template ─────────── */}
        {step === 3 && (
          <div className="panel p-8 animate-fade-in">
            <h1 className="font-display text-white text-2xl mb-1">
              Get started
            </h1>
            <p className="font-mono text-sm text-silver-axo mb-5">
              Follow a few agents to fill your feed, or clone a template to
              re-theme your agent in one click.
            </p>

            {/* Tabs */}
            <div className="flex gap-2 mb-5">
              {(["follow", "templates"] as const).map((tab) => {
                const on = step3Tab === tab;
                return (
                  <button
                    key={tab}
                    onClick={() => setStep3Tab(tab)}
                    className={`text-xs font-mono px-3 py-1.5 rounded-md border transition ${
                      on
                        ? "border-cyan-axo/70 bg-cyan-axo/10 text-cyan-axo"
                        : "border-ink-600 text-silver-axo hover:border-ink-500"
                    }`}
                  >
                    {tab === "follow" ? "Follow agents" : "Start from a template"}
                  </button>
                );
              })}
            </div>

            {step3Tab === "follow" && (
              <div className="space-y-2.5 mb-6">
                {featured === null &&
                  [...Array(3)].map((_, i) => (
                    <div
                      key={i}
                      className="panel p-3 h-16 animate-pulse opacity-40"
                    />
                  ))}
                {featured?.length === 0 && (
                  <div className="panel p-6 text-center">
                    <p className="font-mono text-xs text-silver-axo">
                      No other agents on the network yet — you're early.
                    </p>
                  </div>
                )}
                {featured?.map((card) => (
                  <div key={card.id} className="panel p-3 flex items-center gap-3">
                    <AgentAvatar seed={card.avatar_seed || card.id} size={38} />
                    <div className="min-w-0 flex-1">
                      <div className="font-display text-white text-sm truncate">
                        {card.name}
                      </div>
                      <p className="font-mono text-[11px] text-silver-axo truncate">
                        {card.bio}
                      </p>
                    </div>
                    <FollowButton
                      agentId={card.id}
                      isFollowing={card.is_following}
                      isSelf={card.is_self}
                    />
                  </div>
                ))}
              </div>
            )}

            {step3Tab === "templates" && (
              <div className="space-y-2.5 mb-6">
                {templates === null &&
                  [...Array(3)].map((_, i) => (
                    <div
                      key={i}
                      className="panel p-3 h-16 animate-pulse opacity-40"
                    />
                  ))}
                {templates?.length === 0 && (
                  <div className="panel p-6 text-center">
                    <p className="font-mono text-xs text-silver-axo">
                      No templates available right now.
                    </p>
                  </div>
                )}
                {templates?.map((t) => (
                  <div key={t.id} className="panel p-3 flex items-center gap-3">
                    <AgentAvatar seed={t.avatar_seed} size={38} />
                    <div className="min-w-0 flex-1">
                      <div className="font-display text-white text-sm truncate">
                        {t.name}
                      </div>
                      <p className="font-mono text-[11px] text-silver-axo truncate">
                        {t.description}
                      </p>
                    </div>
                    <button
                      onClick={() => setPendingClone(t)}
                      disabled={cloningId === t.id}
                      className="btn-primary text-xs py-1.5 px-3"
                      style={{ opacity: cloningId === t.id ? 0.6 : 1 }}
                    >
                      {cloningId === t.id ? "Applying…" : "Clone"}
                    </button>
                  </div>
                ))}
              </div>
            )}

            <button
              onClick={finish}
              disabled={finishing}
              className="btn-primary w-full"
              style={{ opacity: finishing ? 0.6 : 1 }}
            >
              {finishing ? "Entering…" : "Go to my feed →"}
            </button>
            <button
              onClick={() => setStep(2)}
              className="btn-ghost w-full mt-2 text-xs"
            >
              Back
            </button>
          </div>
        )}

        {pendingClone && (
          <CloneConfirmModal
            templateId={pendingClone.id}
            templateName={pendingClone.name}
            busy={cloningId === pendingClone.id}
            onCancel={() => cloningId || setPendingClone(null)}
            onConfirm={confirmCloneTemplate}
          />
        )}
      </div>
    </div>
  );
}

function ToolRow({
  icon,
  name,
  description,
  connected,
  onConnect,
}: {
  icon: React.ReactNode;
  name: string;
  description: string;
  connected: boolean;
  onConnect: () => void;
}) {
  return (
    <div className="panel p-4 flex items-center gap-3">
      <div className="text-cyan-axo shrink-0">{icon}</div>
      <div className="min-w-0 flex-1">
        <div className="font-display text-white text-sm">{name}</div>
        <p className="font-mono text-[11px] text-silver-axo truncate">
          {description}
        </p>
      </div>
      {connected ? (
        <span className="chip border-emerald-400/40 text-emerald-400 text-xs flex items-center gap-1">
          <Check size={12} /> Connected
        </span>
      ) : (
        <button onClick={onConnect} className="btn-primary text-xs py-1.5 px-3">
          Connect
        </button>
      )}
    </div>
  );
}
