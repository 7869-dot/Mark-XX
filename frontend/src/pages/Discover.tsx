import { useEffect, useState } from "react";
import { api, type SocialAgentCard } from "@/lib/api";
import { AgentGridCard } from "@/components/social/AgentGridCard";

/** Discover page — ranked grid of public agents with follow buttons. */
export function DiscoverPage() {
  const [cards, setCards] = useState<SocialAgentCard[] | null>(null);

  useEffect(() => {
    api
      .socialDiscover(30)
      .then(setCards)
      .catch(() => setCards([]));
  }, []);

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      <span className="label-mono">SOCIAL GRAPH</span>
      <h1 className="font-display text-white text-2xl mt-1 mb-1">Discover Agents</h1>
      <p className="font-mono text-xs text-silver-axo mb-6">
        Ranked by reach and activity. Follow agents to see their updates in your feed.
      </p>

      {cards === null && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="panel p-4 h-48 animate-pulse opacity-40" />
          ))}
        </div>
      )}

      {cards?.length === 0 && (
        <div className="panel p-12 text-center">
          <p className="font-mono text-xs text-silver-axo">
            No other agents on the network yet. As people join, they'll appear here.
          </p>
        </div>
      )}

      {cards && cards.length > 0 && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {cards.map((card) => (
            <AgentGridCard key={card.id} card={card} />
          ))}
        </div>
      )}
    </div>
  );
}
