import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'poly-dark': '#0d0d14',
        'poly-card': '#13131f',
        'poly-border': '#1e1e2e',
        'poly-text': '#e8e8f0',
        'poly-muted': '#6b6b85',
      },
    },
  },
  plugins: [],
}

export default config
