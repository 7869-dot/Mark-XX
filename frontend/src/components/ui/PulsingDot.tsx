import { classNames } from "@/lib/utils";

const COLORS: Record<string, string> = {
  active: "bg-cyan-axo shadow-[0_0_12px_#00f5d4]",
  idle: "bg-silver-axo/60",
  busy: "bg-amber-axo shadow-[0_0_12px_#ffb347]",
  sleeping: "bg-ink-500",
};

export function PulsingDot({
  status = "active",
  className,
  size = 8,
}: {
  status?: string;
  className?: string;
  size?: number;
}) {
  return (
    <span
      className={classNames(
        "inline-block rounded-full animate-pulse-dot",
        COLORS[status] || COLORS.idle,
        className
      )}
      style={{ width: size, height: size }}
    />
  );
}
