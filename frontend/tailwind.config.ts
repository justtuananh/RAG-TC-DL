import type { Config } from "tailwindcss";

/**
 * Token đọc trực tiếp từ mockup `design/kiemdinh.html`.
 * Phần lớn màu trùng palette mặc định của Tailwind (green/slate/amber/red),
 * chỉ định nghĩa thêm các màu "bề mặt" pha xanh đặc trưng của app.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: "#16A34A", // = green-600
        "brand-dark": "#15803D", // = green-700
        app: "#ECF1EE", // nền toàn app
        sidebar: "#F6F8F7", // nền thanh lịch sử + bong bóng bot
        source: "#F1F4F2", // nền cột nguồn
        line: "#E6EAE8", // viền mảnh chủ đạo
        "row-hover": "#EAEFEC", // hover hàng lịch sử
        highlight: "#FEF6DD", // nền đoạn nguồn được tô sáng
        "page-foot": "#6E8B78", // chân "trang tài liệu"
        "icon-muted": "#A8B2AC", // icon hành động mờ
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
          "0%,100%": { boxShadow: "0 0 0 0 rgba(245,158,11,0)" },
          "50%": { boxShadow: "0 0 0 5px rgba(245,158,11,.22)" },
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
