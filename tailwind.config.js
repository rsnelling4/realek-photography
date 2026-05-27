/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        cream: '#FDFAF6',
        parchment: '#F0E6D9',
        terracotta: '#C17A50',
        'terracotta-dark': '#A3613A',
        'warm-brown': '#8B5E3C',
        'dark-brown': '#2C1810',
        taupe: '#9B8578',
      },
      fontFamily: {
        serif: ['"Playfair Display"', 'Georgia', 'serif'],
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
