import type { Config } from "tailwindcss";

// Palette names kept stable so existing utility classes inherit the Biopunk
// Terminal look without per-page rewrites. Values map to tokens.css.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#050709",
          900: "#080B0F", // --bg-void
          800: "#0D1117", // --bg-surface
          700: "#141B24", // --bg-elevated
          600: "#1C2632", // --bg-overlay
          500: "#2A3A48",
        },
        cyan: {
          axo: "#14D4B2", // --teal-bright
        },
        teal: {
          dim: "#0B3D3A",
          mid: "#0F7A6B",
          bright: "#14D4B2",
        },
        amber: {
          axo: "#FFB300", // --amber-bright
        },
        coral: {
          dim: "#3D1A0B",
          mid: "#C44A1A",
          bright: "#FF7043",
        },
        silver: {
          axo: "#7A8A9E", // --text-secondary
        },
        rose: {
          axo: "#FF7043", // --coral-bright
        },
      },
      textColor: {
        primary: "#E8EDF3",
        secondary: "#7A8A9E",
        muted: "#3D4E61",
      },
      fontFamily: {
        display: ["'Space Mono'", "ui-monospace", "monospace"],
        body: ["'DM Sans'", "ui-sans-serif", "system-ui"],
        mono: ["'JetBrains Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontVariantNumeric: {
        tabular: "tabular-nums",
      },
      animation: {
        "pulse-dot": "pulseDot 2s ease-in-out infinite",
        "slide-in": "slideIn 200ms ease-out",
        "fade-in": "fadeIn 300ms ease-out",
        "bloom": "bloom 600ms ease-out",
        "breathe": "breathe 3s ease-in-out infinite",
      },
      keyframes: {
        pulseDot: {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.55", transform: "scale(1.15)" },
        },
        slideIn: {
          from: { opacity: "0", transform: "translateY(-8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        fadeIn: {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        bloom: {
          "0%": { opacity: "0", transform: "scale(0.6)" },
          "60%": { opacity: "1", transform: "scale(1.05)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        breathe: {
          "0%, 100%": { transform: "scale(1)" },
          "50%": { transform: "scale(1.04)" },
        },
      },
      boxShadow: {
        glow: "0 0 20px rgba(20, 212, 178, 0.15)",
        "glow-strong": "0 0 24px rgba(20, 212, 178, 0.30)",
        amber: "0 0 24px rgba(255, 179, 0, 0.22)",
        coral: "0 0 20px rgba(255, 112, 67, 0.18)",
      },
      backgroundImage: {
        grid:
          "linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)",
      },
    },
  },
  plugins: [],
} satisfies Config;
