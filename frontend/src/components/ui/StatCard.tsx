import type { ReactNode } from "react";
import { CountUp } from "./CountUp";

export function StatCard({
  label,
  value,
  unit,
  icon,
  tone = "default",
}: {
  label: string;
  value: number;
  unit?: string;
  icon?: ReactNode;
  tone?: "default" | "cyan" | "amber";
}) {
  const valueClass =
    tone === "cyan"
      ? "text-cyan-axo"
      : tone === "amber"
      ? "text-amber-axo"
      : "text-white";
  return (
    <div className="panel p-4 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="label-mono">{label}</span>
        {icon}
      </div>
      <div className="flex items-baseline gap-1">
        <CountUp
          value={value}
          className={`font-display font-semibold text-2xl tabular-nums ${valueClass}`}
        />
        {unit && (
          <span className="font-mono text-xs text-silver-axo/70">{unit}</span>
        )}
      </div>
    </div>
  );
}
