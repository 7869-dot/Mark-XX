import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from "recharts";

type PV = Record<string, number>;

const AXES = [
  { key: "openness", label: "Openness" },
  { key: "directness", label: "Directness" },
  { key: "ambition", label: "Ambition" },
  { key: "sociability", label: "Sociability" },
  { key: "risk_tolerance", label: "Risk" },
];

export function PersonalityRadar({
  personality,
  height = 320,
}: {
  personality: PV;
  height?: number;
}) {
  const data = AXES.map((a) => ({
    axis: a.label,
    value: Math.round(((personality[a.key] ?? 0.5) * 100)) ,
  }));

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <RadarChart data={data} outerRadius="75%">
          <PolarGrid stroke="#2E2E33" />
          <PolarAngleAxis
            dataKey="axis"
            tick={{ fill: "#8A8780", fontSize: 11, fontFamily: "IBM Plex Mono" }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={false}
            axisLine={false}
          />
          <Radar
            dataKey="value"
            stroke="#2563EB"
            fill="#2563EB"
            fillOpacity={0.3}
            strokeWidth={1.5}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
