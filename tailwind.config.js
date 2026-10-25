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
          50: '#edf3fb',
          100: '#dce8f6',
          200: '#b9d0ed',
          300: '#90b4e2',
          400: '#6494d4',
          500: '#3f73bf',
          600: '#2f5fa8',
          700: '#254c86',
          800: '#1f3d6b',
          900: '#17324d',
        },
      },
      boxShadow: {
        soft: '0 10px 30px rgba(23, 50, 77, 0.10)',
      },
    },
  },
  plugins: [],
};