import { useEffect, useMemo, useRef, useState } from "react";
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  type Simulation,
} from "d3-force";
import type { PublicAgentProfile } from "@/types";
import { AgentNodeTooltip } from "./AgentNodeTooltip";

type SimNode = {
  id: string;
  name: string;
  reputation: number;
  compatibility: number;
  isMe: boolean;
  x: number;
  y: number;
  fx?: number | null;
  fy?: number | null;
};

function radiusFor(reputation: number, isMe: boolean) {
  if (isMe) return 22;
  // reputation 0..100 → 8px..24px
  return Math.max(8, Math.min(24, 8 + (reputation / 100) * 16));
}

export function AgentGraph({
  selfId,
  selfName,
  others,
  onSelect,
  onConnect,
}: {
  selfId: string;
  selfName: string;
  others: PublicAgentProfile[];
  onSelect?: (id: string) => void;
  onConnect?: (id: string) => Promise<void> | void;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 800, h: 600 });
  const [tick, setTick] = useState(0);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [connectingId, setConnectingId] = useState<string | null>(null);
  const nodesRef = useRef<SimNode[]>([]);
  const simRef = useRef<Simulation<SimNode, undefined> | null>(null);

  const isMobile = size.w < 768;

  useEffect(() => {
    const update = () => {
      const r = wrapRef.current?.getBoundingClientRect();
      if (r) setSize({ w: r.width, h: r.height || 600 });
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  useEffect(() => {
    if (isMobile) return; // graph is desktop-only
    const nodes: SimNode[] = [
      {
        id: selfId,
        name: selfName,
        reputation: 80,
        compatibility: 100,
        isMe: true,
        x: size.w / 2,
        y: size.h / 2,
        fx: size.w / 2,
        fy: size.h / 2,
      },
      ...others.map((o) => ({
        id: o.id,
        name: o.name,
        reputation: o.reputation_score,
        compatibility: o.compatibility_score ?? 50,
        isMe: false,
        x: size.w / 2 + (Math.random() - 0.5) * 200,
        y: size.h / 2 + (Math.random() - 0.5) * 200,
      })),
    ];
    const links = others.map((o) => ({ source: selfId, target: o.id }));
    nodesRef.current = nodes;

    const sim = forceSimulation<SimNode>(nodes)
      .force(
        "link",
        forceLink<SimNode, any>(links)
          .id((d) => d.id)
          .distance(150)
      )
      .force("charge", forceManyBody().strength(-280))
      .force("center", forceCenter(size.w / 2, size.h / 2))
      .force("collide", forceCollide<SimNode>().radius((d) => radiusFor(d.reputation, d.isMe) + 14));

    sim.on("tick", () => setTick((t) => t + 1));
    simRef.current = sim;
    return () => {
      sim.stop();
    };
  }, [selfId, selfName, others, size.w, size.h, isMobile]);

  const links = useMemo(
    () => others.map((o) => ({ source: selfId, target: o.id })),
    [others, selfId]
  );

  const hovered = others.find((o) => o.id === hoverId) || null;
  const hoveredNode = nodesRef.current.find((n) => n.id === hoverId);

  const handleConnect = async (id: string) => {
    if (!onConnect) return;
    setConnectingId(id);
    try {
      await onConnect(id);
    } finally {
      setConnectingId(null);
    }
  };

  // Mobile: collapse to a ranked list.
  if (isMobile) {
    return (
      <div ref={wrapRef} className="w-full p-4 space-y-2">
        <p className="label-mono mb-2">NETWORK · LIST VIEW</p>
        {others.map((o) => (
          <div
            key={o.id}
            className="panel p-3 flex items-center justify-between"
            onClick={() => onSelect?.(o.id)}
          >
            <div className="min-w-0">
              <div className="font-display text-white text-sm truncate">
                {o.name}
              </div>
              <div className="font-mono text-[11px] text-silver-axo truncate">
                {o.user_name} · REP {Math.round(o.reputation_score)} · FIT{" "}
                {Math.round(o.compatibility_score ?? 0)}
              </div>
            </div>
            <button
              className="btn-primary text-[11px] py-1 shrink-0"
              onClick={(e) => {
                e.stopPropagation();
                handleConnect(o.id);
              }}
              disabled={connectingId === o.id}
            >
              {connectingId === o.id ? "…" : "Connect"}
            </button>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div ref={wrapRef} className="relative w-full h-full min-h-[60vh]">
      <svg className="w-full h-full" key={tick === 0 ? "init" : "live"}>
        {links.map((l, i) => {
          const s = nodesRef.current.find((n) => n.id === l.source);
          const t = nodesRef.current.find((n) => n.id === l.target);
          if (!s || !t) return null;
          return (
            <line
              key={i}
              x1={s.x}
              y1={s.y}
              x2={t.x}
              y2={t.y}
              stroke="rgba(0,245,212,0.12)"
              strokeWidth={1}
            />
          );
        })}
        {nodesRef.current.map((n) => {
          const r = radiusFor(n.reputation, n.isMe);
          const color = n.isMe
            ? "#00f5d4"
            : `hsl(${160 + n.compatibility * 0.6}, 70%, 60%)`;
          return (
            <g
              key={n.id}
              style={{ cursor: "pointer" }}
              onMouseEnter={() => !n.isMe && setHoverId(n.id)}
              onMouseLeave={() => setHoverId(null)}
              onClick={() => !n.isMe && onSelect?.(n.id)}
            >
              <circle cx={n.x} cy={n.y} r={r + 6} fill={color} opacity={0.08} />
              <circle cx={n.x} cy={n.y} r={r} fill={color} opacity={0.85} />
              <text
                x={n.x}
                y={n.y + r + 14}
                textAnchor="middle"
                fill="#8892a4"
                fontFamily="IBM Plex Mono"
                fontSize="10"
              >
                {n.name.length > 18 ? n.name.slice(0, 17) + "…" : n.name}
              </text>
            </g>
          );
        })}
      </svg>

      {hovered && hoveredNode && (
        <AgentNodeTooltip
          agent={hovered}
          x={hoveredNode.x}
          y={hoveredNode.y}
          connecting={connectingId === hovered.id}
          onConnect={() => handleConnect(hovered.id)}
        />
      )}
    </div>
  );
}
