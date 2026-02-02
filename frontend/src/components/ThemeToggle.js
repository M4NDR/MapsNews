// src/components/ThemeToggle.jsx
import React from 'react';
import useDarkMode from '../hooks/useDarkMode';
import '../styles/ThemeToggle.css';

export default function ThemeToggle() {
  const [theme, setTheme] = useDarkMode();

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  };

  const isDark = theme === 'dark';

  return (
    <button
      className="theme-toggle"
      onClick={toggleTheme}
      aria-label="Переключить тему"
    >
      {isDark ? 'Светлая' : 'Тёмная'}
    </button>
  );
}