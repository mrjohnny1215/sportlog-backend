/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        board: {
          bg: "#0B0E14",
          card: "#151922",
          card2: "#1B2230",
          border: "#232936",
        },
        led: {
          win: "#00FF87",
          lose: "#FF495C",
          gold: "#FFD000",
          nrfi: "#FF8C00",
          yrfi: "#A855F7",
          flame: "#FF3B30",
        },
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      boxShadow: {
        glow: "0 0 8px rgba(0,255,135,0.45)",
        "glow-gold": "0 0 10px rgba(255,208,0,0.5)",
        "glow-red": "0 0 10px rgba(255,73,92,0.5)",
      },
      keyframes: {
        pulseLed: {
          "0%,100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
      },
      animation: {
        pulseLed: "pulseLed 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
