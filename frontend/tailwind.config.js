/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["'Sora Variable'", "system-ui", "sans-serif"],
        sans: ["'IBM Plex Sans'", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"],
      },
      colors: {
        ink: {
          950: "#070c18",
          900: "#0b1326",
          850: "#0f1a33",
          800: "#152444",
          700: "#1e335a",
          600: "#2a467a",
        },
        volt: {
          DEFAULT: "#0ea5e9", // Precision Industrial Sky/Cyan
          soft: "#38bdf8",
          deep: "#0284c7",
        },
        pass: {
          DEFAULT: "#10b981", // Industrial PASS Green
          dark: "#059669",
        },
        review: {
          DEFAULT: "#f59e0b", // Industrial REVIEW Amber
          dark: "#d97706",
        },
        fail: {
          DEFAULT: "#ef4444", // Industrial FAIL Red
          dark: "#dc2626",
        },
      },
      boxShadow: {
        subtle: "0 1px 3px 0 rgba(0, 0, 0, 0.3), 0 1px 2px -1px rgba(0, 0, 0, 0.3)",
        panel: "0 2px 8px -1px rgba(0, 0, 0, 0.4)",
        focus: "0 0 0 2px rgba(14, 165, 233, 0.35)",
      },
    },
  },
  plugins: [],
};
