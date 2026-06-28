import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Material Design 3 tokens — từ design.html
        primary: "#006130",
        "on-primary": "#ffffff",
        "primary-container": "#107c41",
        "on-primary-container": "#b6ffc5",
        secondary: "#515f74",
        "on-secondary": "#ffffff",
        "secondary-container": "#d5e3fd",
        "on-secondary-container": "#57657b",
        background: "#faf8ff",
        "on-background": "#131b2e",
        surface: "#faf8ff",
        "on-surface": "#131b2e",
        "surface-variant": "#dae2fd",
        "on-surface-variant": "#3f4940",
        outline: "#6f7a6f",
        "outline-variant": "#becabd",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#f2f3ff",
        "surface-container": "#eaedff",
        "surface-container-high": "#e2e7ff",
        "surface-container-highest": "#dae2fd",
        "inverse-primary": "#7ada95",
        error: "#ba1a1a",
        "error-container": "#ffdad6",
        // Legacy aliases
        brand: "#006130",
        "brand-dark": "#004f27",
        app: "#faf8ff",
        sidebar: "#ffffff",
        "bot-bubble": "#f2f3ff",
        source: "#eaedff",
        line: "#becabd",
        "row-hover": "#dae2fd",
        highlight: "#FEF6DD",
        "page-foot": "#6f7a6f",
        "icon-muted": "#6f7a6f",
      },
      fontFamily: {
        sans: ["'Be Vietnam Pro'", "system-ui", "-apple-system", "sans-serif"],
        serif: ["'Lora'", "Georgia", "serif"],
      },
      keyframes: {
        spin: { to: { transform: "rotate(360deg)" } },
        pulseDot: { "0%,100%": { opacity: "1" }, "50%": { opacity: ".35" } },
        fadeUp: { from: { transform: "translateY(7px)", opacity: "0" }, to: { transform: "translateY(0)", opacity: "1" } },
        hlGlow: {
          "0%,100%": { boxShadow: "0 0 0 0 rgba(0,97,48,0)" },
          "50%": { boxShadow: "0 0 0 5px rgba(0,97,48,.18)" },
        },
      },
      animation: {
        spin: "spin .8s linear infinite",
        pulseDot: "pulseDot 2s ease-in-out infinite",
        fadeUp: "fadeUp .25s ease-out",
        hlGlow: "hlGlow 2.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
