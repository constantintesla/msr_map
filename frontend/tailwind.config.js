/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      screens: {
        'landscape-phone': { raw: '(orientation: landscape) and (max-width: 767px)' },
      },
      colors: {
        bg: '#000000',
        text: '#E2E8F0',
        sideA: '#3B82F6',
        sideB: '#EF4444',
        warning: '#F59E0B',
      },
      minHeight: {
        touch: '60px',
      },
    },
  },
  plugins: [],
}
