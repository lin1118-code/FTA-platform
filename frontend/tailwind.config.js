/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { ink: "#172033", canvas: "#f5f7fb", accent: "#2f6fed" },
      boxShadow: { card: "0 8px 24px rgba(20, 34, 62, 0.07)" },
    },
  },
  plugins: [],
};
