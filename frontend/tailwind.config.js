/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:       '#0C0D0E',
        card:     '#12151C',
        border:   '#1F2937',
        text:     '#FFFFFF',
        sub:      '#9CA3AF',
        accent:   '#3B82F6',
        green:    '#22C55E',
        red:      '#EF4444',
        amber:    '#F59E0B',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      keyframes: {
        pageFadeIn: {
          '0%':   { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        'page-enter': 'pageFadeIn 0.25s ease-out both',
        shimmer:      'shimmer 1.5s infinite',
      },
    },
  },
  plugins: [],
}
