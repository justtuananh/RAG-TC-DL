import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Xanh quân đội hiện đại (forest) - theme token duy nhất, xem thêm src/theme.ts
        primary: "#2D6A43",
        "on-primary": "#ffffff",
        "primary-container": "#E8F3EC",
        "on-primary-container": "#1E4D30",
        secondary: "#46524B",
        "on-secondary": "#ffffff",
        "secondary-container": "#E8F3EC",
        "on-secondary-container": "#1E4D30",
        background: "#F5F7F6",
        "on-background": "#0F1A14",
        surface: "#FFFFFF",
        "on-surface": "#0F1A14",
        "surface-variant": "#E9EEEB",
        "on-surface-variant": "#46524B",
        outline: "#6B7770",
        "outline-variant": "#E1E7E3",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#F3F6F4",
        "surface-container": "#E9EEEB",
        "surface-container-high": "#E1E7E3",
        "surface-container-highest": "#BFDCC9",
        "inverse-primary": "#BFDCC9",
        error: "#C8102E",
        "error-container": "#FDF0F1",
        // Legacy aliases
        brand: "#2D6A43",
        "brand-dark": "#1E4D30",
        app: "#F5F7F6",
        sidebar: "#0E1A13",
        "bot-bubble": "#F3F6F4",
        source: "#E9EEEB",
        line: "#E1E7E3",
        "line-strong": "#C7D1CB",
        "row-hover": "#E8F3EC",
        "accent-soft-border": "#BFDCC9",
        "danger-border": "#F5C2C9",
        highlight: "#FFF3C4",
        "page-foot": "#6B7770",
        "icon-muted": "#6B7770",
      },
      fontFamily: {
        sans: ["'Be Vietnam Pro'", "system-ui", "-apple-system", "sans-serif"],
        serif: ["'Lora'", "Georgia", "serif"],
      },
      boxShadow: {
        // Bóng đổ theo accent xanh rừng cho nút/hàng động (thay các mã rgba viết cứng)
        brand: "0 2px 6px rgba(45,106,67,.3)",
        "brand-sm": "0 1px 3px rgba(45,106,67,.3)",
        "brand-row": "0 6px 18px -8px rgba(45,106,67,.24)",
        "brand-lg": "0 10px 26px -12px rgba(45,106,67,.5)",
        focus: "0 0 0 3px #E8F3EC",
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
