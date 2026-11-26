/** @type {import('tailwindcss').Config} */
module.exports = {
  // Tailwind สแกนไฟล์เหล่านี้เพื่อสร้างเฉพาะ class ที่ใช้จริง (ไฟล์ CSS เล็กมาก)
  content: [
    "./templates/**/*.html",
    "./crm/templates/**/*.html",
    "./crm/**/*.py",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Noto Sans Thai"', "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [require("@tailwindcss/forms")],
};
