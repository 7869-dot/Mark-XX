import type { Config } from "tailwindcss";

/* Legacy color names (ink, cyan, teal, amber, coral, silver, rose) are kept so
 * existing utility classes don't break — but every value now points at the new
 * professional "McKinsey × Notion" palette. The semantic mapping:
 *   - any "ink" / dark background → light off-white surfaces
 *   - any "cyan" / "teal" accent  → McKinsey blue
 *   - "amber"                     → muted gold
 *   - "coral" / "rose"            → restrained danger red
 *   - "silver"                    → secondary text grey
 * New code should prefer the explicit names: paper, ink, accent, gold, success.
 */
const ACCENT = "#1B4FD8";
const ACCENT_HOVER = "#1644BD";
const GOLD = "#D4A017";
const SUCCESS = "#1A7F5A";
const DANGER = "#B3261E";
const TEXT_PRIMARY = "#1A1A1A";
const TEXT_SECONDARY = "#6B6B6B";
const TEXT_MUTED = "#9A9A9A";
const PAPER = "#F7F6F3";
const PAPER_2 = "#FFFFFF";
const PAPER_3 = "#FAFAF8";
const BORDER = "#E2DFD8";
const SIDEBAR = "#1C1C1E";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // New explicit names
        paper: { DEFAULT: PAPER, surface: PAPER_2, alt: PAPER_3 },
        sidebar: { DEFAULT: SIDEBAR, hover: "#2A2A2D" },
        accent: { DEFAULT: ACCENT, hover: ACCENT_HOVER, soft: "rgba(27,79,216,0.10)" },
        gold: { DEFAULT: GOLD, soft: "rgba(212,160,23,0.12)" },
        success: { DEFAULT: SUCCESS, soft: "rgba(26,127,90,0.10)" },
        danger: { DEFAULT: DANGER, soft: "rgba(179,38,30,0.08)" },

        // Legacy aliases — values remapped to the new palette
        ink: {
          950: PAPER_2,
          900: PAPER,
          800: PAPER_2,
          700: PAPER_3,
          600: PAPER_3,
          500: BORDER,
        },
        cyan: { axo: ACCENT },
        teal: { dim: "rgba(27,79,216,0.08)", mid: ACCENT, bright: ACCENT },
        amber: { axo: GOLD },
        coral: { dim: "rgba(179,38,30,0.06)", mid: DANGER, bright: DANGER },
        silver: { axo: TEXT_SECONDARY },
        rose: { axo: DANGER },
      },
      textColor: {
        primary: TEXT_PRIMARY,
        secondary: TEXT_SECONDARY,
        muted: TEXT_MUTED,
      },
      fontFamily: {
        display: ["'DM Serif Display'", "Georgia", "serif"],
        body: ["'IBM Plex Sans'", "system-ui", "-apple-system", "sans-serif"],
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
        glow: "0 2px 12px rgba(15,17,22,0.06)",
        "glow-strong": "0 8px 32px rgba(15,17,22,0.10)",
        amber: "0 2px 12px rgba(212,160,23,0.18)",
        coral: "0 2px 12px rgba(179,38,30,0.12)",
      },
      backgroundImage: {
        grid:
          "linear-gradient(rgba(15,17,22,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(15,17,22,0.04) 1px, transparent 1px)",
      },
    },
  },
  plugins: [],
} satisfies Config;
