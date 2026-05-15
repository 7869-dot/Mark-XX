import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#04060b",
          900: "#080c14",
          800: "#0d1320",
          700: "#141b2c",
          600: "#1c2438",
          500: "#2a334a",
        },
        cyan: {
          axo: "#00f5d4",
        },
        amber: {
          axo: "#ffb347",
        },
        silver: {
          axo: "#8892a4",
        },
        rose: {
          axo: "#ff6b6b",
        },
      },
      fontFamily: {
        display: ["'Space Grotesk'", "ui-sans-serif", "system-ui"],
        mono: ["'IBM Plex Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontVariantNumeric: {
        tabular: "tabular-nums",
      },
      animation: {
        "pulse-dot": "pulseDot 2s ease-in-out infinite",
        "slide-in": "slideIn 200ms ease-out",
        "fade-in": "fadeIn 300ms ease-out",
        "bloom": "bloom 600ms ease-out",
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
      },
      boxShadow: {
        glow: "0 0 24px rgba(0, 245, 212, 0.25)",
        amber: "0 0 24px rgba(255, 179, 71, 0.22)",
      },
      backgroundImage: {
        grid:
          "linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px)",
      },
    },
  },
  plugins: [],
} satisfies Config;
