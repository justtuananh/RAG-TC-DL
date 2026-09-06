import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Signal Blue — theme token duy nhất, xem thêm src/theme.ts
        primary: "#2454E0",
        "on-primary": "#ffffff",
        "primary-container": "#E9EFFF",
        "on-primary-container": "#173CAE",
        secondary: "#475467",
        "on-secondary": "#ffffff",
        "secondary-container": "#E9EFFF",
        "on-secondary-container": "#173CAE",
        background: "#F3F5F8",
        "on-background": "#101828",
        surface: "#FFFFFF",
        "on-surface": "#101828",
        "surface-variant": "#E8ECF2",
        "on-surface-variant": "#475467",
        outline: "#7C8896",
        "outline-variant": "#DEE3EA",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#F1F4F9",
        "surface-container": "#E8ECF2",
        "surface-container-high": "#DEE3EA",
        "surface-container-highest": "#C9D8FF",
        "inverse-primary": "#C9D8FF",
        error: "#DC2626",
        "error-container": "#FEF2F2",
        // Legacy aliases
        brand: "#2454E0",
        "brand-dark": "#173CAE",
        app: "#F3F5F8",
        sidebar: "#10151F",
        "bot-bubble": "#F1F4F9",
        source: "#E8ECF2",
        line: "#DEE3EA",
        "row-hover": "#E9EFFF",
        highlight: "#FFF3C4",
        "page-foot": "#7C8896",
        "icon-muted": "#7C8896",
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
          "0%,100%": { boxShadow: "0 0 0 0 rgba(243,180,41,0)" },
          "50%": { boxShadow: "0 0 0 5px rgba(243,180,41,.28)" },
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
