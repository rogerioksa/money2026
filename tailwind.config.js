/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/money99/**/*.html',
    './src/money99/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#edf8f2',
          100: '#d7f0e2',
          200: '#afdccc',
          300: '#81c2aa',
          400: '#4ea57f',
          500: '#2d7d5e',
          600: '#1f5c3a',
          700: '#184a31',
          800: '#123a2a',
          900: '#0d2d21',
        },
      },
      boxShadow: {
        soft: '0 10px 30px rgba(19, 52, 36, 0.10)',
      },
    },
  },
  plugins: [],
};
