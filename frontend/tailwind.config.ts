import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Xanh quân đội — theme token duy nhất, xem thêm src/theme.ts
        primary: "#4B5E27",
        "on-primary": "#ffffff",
        "primary-container": "#EDF1E1",
        "on-primary-container": "#34431A",
        secondary: "#4C5442",
        "on-secondary": "#ffffff",
        "secondary-container": "#EDF1E1",
        "on-secondary-container": "#34431A",
        background: "#F4F5EF",
        "on-background": "#1A1F14",
        surface: "#FFFFFF",
        "on-surface": "#1A1F14",
        "surface-variant": "#E6E9DC",
        "on-surface-variant": "#4C5442",
        outline: "#767E6C",
        "outline-variant": "#DADFCC",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#F0F2E9",
        "surface-container": "#E6E9DC",
        "surface-container-high": "#DADFCC",
        "surface-container-highest": "#CFD9B5",
        "inverse-primary": "#CFD9B5",
        error: "#C8102E",
        "error-container": "#FDF0F1",
        // Legacy aliases
        brand: "#4B5E27",
        "brand-dark": "#34431A",
        app: "#F4F5EF",
        sidebar: "#1E2814",
        "bot-bubble": "#F0F2E9",
        source: "#E6E9DC",
        line: "#DADFCC",
        "line-strong": "#BEC6AC",
        "row-hover": "#EDF1E1",
        "accent-soft-border": "#CFD9B5",
        "danger-border": "#F5C2C9",
        highlight: "#FFF3C4",
        "page-foot": "#767E6C",
        "icon-muted": "#767E6C",
      },
      fontFamily: {
        sans: ["'Be Vietnam Pro'", "system-ui", "-apple-system", "sans-serif"],
        serif: ["'Lora'", "Georgia", "serif"],
      },
      boxShadow: {
        // Bóng đổ theo accent ô liu cho nút/hàng động (thay các mã rgba viết cứng)
        brand: "0 2px 6px rgba(75,94,39,.3)",
        "brand-sm": "0 1px 3px rgba(75,94,39,.3)",
        "brand-row": "0 6px 18px -8px rgba(75,94,39,.24)",
        "brand-lg": "0 10px 26px -12px rgba(75,94,39,.5)",
        focus: "0 0 0 3px #EDF1E1",
      },
      keyframes: {
        spin: { to: { transform: "rotate(360deg)" } },
        pulseDot: { "0%,100%": { opacity: "1" }, "50%": { opacity: ".35" } },
        fadeUp: { from: { transform: "translateY(7px)", opacity: "0" }, to: { transform: "translateY(0)", opacity: "1" } },
        hlGlow: {
          "0%,100%": { boxShadow: "0 0 0 0 rgba(229,183,0,0)" },
          "50%": { boxShadow: "0 0 0 5px rgba(229,183,0,.28)" },
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
