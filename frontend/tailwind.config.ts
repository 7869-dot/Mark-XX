import type { Config } from "tailwindcss";

/* Dark-first palette. Legacy color names (ink, cyan, teal, amber, coral,
 * silver, rose) are kept so existing utility classes don't break — but every
 * value now points at the new dark tokens. */
const ACCENT_BLUE = "#2563EB";
const ACCENT_BLUE_HOVER = "#1D4ED8";
const ACCENT_BLUE_MUTED = "#1E3A8A";
const ACCENT_GOLD = "#B8860B";
const ACCENT_GREEN = "#16A34A";
const ACCENT_RED = "#DC2626";
const TEXT_PRIMARY = "#E8E6E1";
const TEXT_SECONDARY = "#8A8780";
const TEXT_TERTIARY = "#4A4845";
const BG_BASE = "#0F0F10";
const BG_SURFACE = "#1A1A1D";
const BG_ELEVATED = "#242428";
const BG_SIDEBAR = "#111113";
const BORDER_SUBTLE = "#252528";
const BORDER_DEFAULT = "#2E2E33";
const BORDER_STRONG = "#3D3D44";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // New explicit names
        bg: { base: BG_BASE, surface: BG_SURFACE, elevated: BG_ELEVATED, sidebar: BG_SIDEBAR },
        accent: {
          blue: ACCENT_BLUE,
          "blue-hover": ACCENT_BLUE_HOVER,
          "blue-muted": ACCENT_BLUE_MUTED,
          gold: ACCENT_GOLD,
          green: ACCENT_GREEN,
          red: ACCENT_RED,
        },
        border: {
          subtle: BORDER_SUBTLE,
          DEFAULT: BORDER_DEFAULT,
          strong: BORDER_STRONG,
        },
        // Legacy aliases — values remapped to the new dark palette
        ink: {
          950: "#070708",
          900: BG_BASE,
          800: BG_SURFACE,
          700: BG_ELEVATED,
          600: "#2C2C30",
          500: BORDER_STRONG,
        },
        cyan: { axo: ACCENT_BLUE },
        teal: { dim: "rgba(37,99,235,0.10)", mid: ACCENT_BLUE, bright: ACCENT_BLUE },
        amber: { axo: ACCENT_GOLD },
        coral: { dim: "rgba(220,38,38,0.10)", mid: ACCENT_RED, bright: ACCENT_RED },
        silver: { axo: TEXT_SECONDARY },
        rose: { axo: ACCENT_RED },
        paper: { DEFAULT: BG_BASE, surface: BG_SURFACE, alt: BG_ELEVATED },
        sidebar: { DEFAULT: BG_SIDEBAR, hover: "#2A2A2D" },
        gold: { DEFAULT: ACCENT_GOLD, soft: "rgba(184,134,11,0.14)" },
        success: { DEFAULT: ACCENT_GREEN, soft: "rgba(22,163,74,0.14)" },
        danger: { DEFAULT: ACCENT_RED, soft: "rgba(220,38,38,0.12)" },
      },
      textColor: {
        primary: TEXT_PRIMARY,
        secondary: TEXT_SECONDARY,
        muted: TEXT_TERTIARY,
        tertiary: TEXT_TERTIARY,
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
        glow: "0 1px 3px rgba(0,0,0,0.4)",
        "glow-strong": "0 4px 16px rgba(0,0,0,0.5)",
        amber: "0 4px 16px rgba(184,134,11,0.30)",
        coral: "0 4px 16px rgba(220,38,38,0.25)",
      },
      backgroundImage: {
        grid:
          "linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)",
      },
    },
  },
  plugins: [],
} satisfies Config;
