/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        purplle: {
          50: "#faf5ff",
          500: "#9333ea",
          700: "#7e22ce",
          900: "#581c87",
        },
      },
    },
  },
  plugins: [],
};
