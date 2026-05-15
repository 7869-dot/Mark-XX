import { useEffect, useState } from "react";
import { timeAgo } from "@/lib/utils";

export function TimeAgo({ iso, className }: { iso: string; className?: string }) {
  const [label, setLabel] = useState(() => timeAgo(iso));
  useEffect(() => {
    const t = setInterval(() => setLabel(timeAgo(iso)), 30_000);
    return () => clearInterval(t);
  }, [iso]);
  return <span className={className}>{label}</span>;
}
