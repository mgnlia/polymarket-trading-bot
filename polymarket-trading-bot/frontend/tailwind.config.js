/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        poly: {
          green: '#00C48C',
          red: '#FF4D4F',
          blue: '#1890FF',
          dark: '#0D1117',
          card: '#161B22',
          border: '#30363D',
          text: '#E6EDF3',
          muted: '#8B949E',
        },
      },
    },
  },
  plugins: [],
}
