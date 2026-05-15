import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { FeedItem } from "@/types";
import { FeedItemCard } from "./FeedItem";

export function ActivityFeed() {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [freshIds, setFreshIds] = useState<Set<string>>(new Set());
  const offsetRef = useRef(0);
  const latestTsRef = useRef<string>("");

  // Initial load.
  const initialLoad = useCallback(async () => {
    try {
      const res = await api.getFeed(0, 30);
      setItems(res.items);
      offsetRef.current = res.next_offset;
      latestTsRef.current = res.items[0]?.timestamp ?? "";
    } finally {
      setLoading(false);
    }
  }, []);

  // Poll: fetch the head and PREPEND only items newer than what we have.
  const poll = useCallback(async () => {
    try {
      const res = await api.getFeed(0, 30);
      const known = latestTsRef.current;
      const incoming = known
        ? res.items.filter((it) => it.timestamp > known)
        : [];
      if (incoming.length) {
        latestTsRef.current = res.items[0].timestamp;
        setItems((prev) => {
          const ids = new Set(prev.map((p) => p.id));
          const merged = [...incoming.filter((i) => !ids.has(i.id)), ...prev];
          return merged;
        });
        setFreshIds(new Set(incoming.map((i) => i.id)));
        setTimeout(() => setFreshIds(new Set()), 1200);
      }
    } catch {
      /* polling errors are non-fatal and already toasted */
    }
  }, []);

  const loadMore = useCallback(async () => {
    const res = await api.getFeed(offsetRef.current, 20);
    setItems((prev) => {
      const ids = new Set(prev.map((p) => p.id));
      return [...prev, ...res.items.filter((i) => !ids.has(i.id))];
    });
    offsetRef.current = res.next_offset;
  }, []);

  useEffect(() => {
    initialLoad();
    const id = setInterval(poll, 30_000);
    return () => clearInterval(id);
  }, [initialLoad, poll]);

  if (loading) {
    return (
      <div className="space-y-3">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="panel p-4 h-20 animate-pulse opacity-40" />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="panel p-10 text-center">
        <div className="font-display text-white text-base mb-2">
          The feed is quiet for now.
        </div>
        <p className="font-mono text-xs text-silver-axo">
          Your agent is settling in. Tasks, interactions, and milestones will
          surface here as they happen.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {items.map((it) => (
        <div
          key={it.id}
          className={freshIds.has(it.id) ? "animate-slide-in" : ""}
        >
          <FeedItemCard item={it} onAction={poll} />
        </div>
      ))}
      <div className="text-center pt-2">
        <button onClick={loadMore} className="btn-ghost text-xs">
          Load more
        </button>
      </div>
    </div>
  );
}
