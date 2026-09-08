/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#0f3d2e",
          light: "#1a5c45",
          dark: "#08281e",
          gold: "#c9a24b",
        },
      },
      fontFamily: {
        display: ["\"Playfair Display\"", "serif"],
        sans: ["\"Inter\"", "sans-serif"],
      },
    },
  },
  plugins: [],
};
