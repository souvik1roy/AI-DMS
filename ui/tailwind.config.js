/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", "[data-theme='dark']"],
  theme: {
    extend: {
      colors: {
        // ---- Semantic tokens (CSS-var backed; swap per theme) ----------
        canvas:  "rgb(var(--canvas) / <alpha-value>)",
        sunken:  "rgb(var(--sunken) / <alpha-value>)",
        border:  "rgb(var(--border) / <alpha-value>)",
        ink: {
          1: "rgb(var(--ink-1) / <alpha-value>)",
          2: "rgb(var(--ink-2) / <alpha-value>)",
          3: "rgb(var(--ink-3) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "rgb(var(--accent) / <alpha-value>)",
          soft:    "rgb(var(--accent-soft) / <alpha-value>)",
          ink:     "rgb(var(--accent-ink) / <alpha-value>)",
        },
        // ---- Surface (semantic; legacy keys preserved) -----------------
        // `surface` is also exposed as a bare colour so `bg-surface` works,
        // and the legacy `surface.muted` / `surface.sunken` / `surface.border`
        // keys keep resolving in existing code.
        surface: Object.assign(
          (...args) => `rgb(var(--surface) / ${args[0] ?? 1})`,
          {
            DEFAULT: "rgb(var(--surface) / <alpha-value>)",
            muted:   "rgb(var(--canvas) / <alpha-value>)",
            sunken:  "rgb(var(--sunken) / <alpha-value>)",
            border:  "rgb(var(--border) / <alpha-value>)",
          }
        ),
        // ---- Legacy brand palette (light-mode hex; dark adapts via CSS) -
        brand: {
          50:  "rgb(var(--brand-50) / <alpha-value>)",
          100: "rgb(var(--brand-100) / <alpha-value>)",
          200: "rgb(var(--brand-200) / <alpha-value>)",
          300: "rgb(var(--brand-300) / <alpha-value>)",
          400: "rgb(var(--brand-400) / <alpha-value>)",
          500: "rgb(var(--brand-500) / <alpha-value>)",
          600: "rgb(var(--brand-600) / <alpha-value>)",
          700: "rgb(var(--brand-700) / <alpha-value>)",
          800: "rgb(var(--brand-800) / <alpha-value>)",
          900: "rgb(var(--brand-900) / <alpha-value>)",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ['"Geist"', "Inter", "ui-sans-serif", "sans-serif"],
        serif: ['"Source Serif 4"', '"Charter"', "Georgia", "serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      boxShadow: {
        // Legacy alias used in many places — keep working.
        card:    "0 1px 2px rgb(var(--shadow) / 0.04), 0 1px 3px rgb(var(--shadow) / 0.05)",
        sidebar: "1px 0 0 rgb(var(--border) / 1)",
        // New elevation tiers.
        "elev-1": "0 1px 2px rgb(var(--shadow) / 0.04), 0 1px 1px rgb(var(--shadow) / 0.03)",
        "elev-2": "0 4px 12px rgb(var(--shadow) / 0.06), 0 2px 4px rgb(var(--shadow) / 0.04)",
        "elev-3": "0 12px 32px rgb(var(--shadow) / 0.08), 0 4px 8px rgb(var(--shadow) / 0.06)",
        ring:    "0 0 0 3px rgb(var(--accent) / 0.18)",
      },
      borderRadius: {
        card: "14px",
        chip: "999px",
      },
      transitionTimingFunction: {
        spring: "cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
};
