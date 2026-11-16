/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f1f0ff", 100: "#e5e3ff", 200: "#cfcbff", 300: "#b0a8ff", 400: "#8c7dff", 500: "#6d5bf5",
          600: "#5b3fe8", 700: "#4c30c9", 800: "#3d28a1", 900: "#241a63", 950: "#150f3d",
        },
        accent: { 400: "#22d3ee", 500: "#06b6d4", 600: "#0891b2" },
      },
      fontFamily: {
        sans: ['"Inter"', '"Segoe UI Variable"', '"Segoe UI"', "system-ui", "-apple-system", "Roboto", "sans-serif"],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(15,23,42,0.04), 0 8px 24px -12px rgba(15,23,42,0.12)",
        lift: "0 2px 4px rgba(15,23,42,0.05), 0 16px 32px -12px rgba(76,48,201,0.25)",
        glow: "0 8px 24px -8px rgba(91,63,232,0.55)",
      },
      keyframes: {
        fadeUp: { "0%": { opacity: "0", transform: "translateY(8px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
        float: { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-10px)" } },
      },
      animation: { "fade-up": "fadeUp .35s ease-out both", float: "float 7s ease-in-out infinite" },
    },
  },
  plugins: [],
};
