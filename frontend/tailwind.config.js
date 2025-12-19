/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0a0a0a",
        foreground: "#ededed",
        card: "#161616",
        "card-foreground": "#ffffff",
        primary: "#10b981", // Emerald 500
        "primary-foreground": "#ffffff",
        secondary: "#3b82f6", // Blue 500
        "secondary-foreground": "#ffffff",
        muted: "#262626",
        "muted-foreground": "#a3a3a3",
        accent: "#f59e0b", // Amber 500
        "accent-foreground": "#ffffff",
        destructive: "#ef4444",
        "destructive-foreground": "#ffffff",
        border: "#262626",
        input: "#262626",
        ring: "#10b981",
      },
      borderRadius: {
        lg: "0.5rem",
        md: "calc(0.5rem - 2px)",
        sm: "calc(0.5rem - 4px)",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Menlo", "Monaco", "Courier New", "monospace"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
}
