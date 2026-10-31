/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#05070b", 900: "#080b11", 850: "#0b0f16", 800: "#0f141c", 750: "#131924", 700: "#1a2130", 600: "#252e40", 500: "#3a4559" },
        fog: { 100: "#e8edf5", 200: "#c9d2e0", 300: "#9aa6ba", 400: "#6f7b91", 500: "#535e72" },
        cyan: { 300: "#67e8f9", 400: "#22d3ee", 500: "#06b6d4", 600: "#0891b2" },
        risk: { low: "#34d399", medium: "#fbbf24", high: "#fb923c", critical: "#f43f5e" },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(34,211,238,.25), 0 0 24px -6px rgba(34,211,238,.35)",
        card: "0 1px 0 0 rgba(255,255,255,.03) inset, 0 12px 32px -16px rgba(0,0,0,.6)",
      },
    },
  },
  plugins: [],
};
