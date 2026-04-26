/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        surface:  "#0D1117",
        panel:    "#161B22",
        overlay:  "#1C2128",
        border:   "#21262D",
        accent:   "#58A6FF",
        muted:    "#6E7681",
        primary:  "#C9D1D9",
        n1:       "#7C8FA6",
        n2:       "#3D9A6F",
        n3:       "#B07D3A",
        n4:       "#9B5A8A",
        n5:       "#4A7FC1",
        n6:       "#A8892B",
        n7:       "#6B5EA8",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Menlo", "monospace"],
        ui:   ["Barlow", "sans-serif"],
      },
      fontSize: {
        "2xs": ["10px", "14px"],
        xs:    ["11px", "16px"],
        sm:    ["12px", "18px"],
        base:  ["13px", "20px"],
        md:    ["14px", "22px"],
      },
      borderRadius: {
        none:    "0",
        sm:      "2px",
        DEFAULT: "3px",
        md:      "4px",
      },
    },
  },
  plugins: [],
};
