// src/hooks/useDarkMode.js
import { useState, useEffect } from 'react';

export default function useDarkMode() {
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('theme');
    return saved || 'system'; // по умолчанию — системная
  });

  useEffect(() => {
    localStorage.setItem('theme', theme);

    // Убираем старые классы
    document.body.classList.remove('dark-mode', 'light-mode');
    document.body.removeAttribute('data-theme');

    if (theme === 'dark') {
      document.body.setAttribute('data-theme', 'dark');
    } else if (theme === 'light') {
      document.body.setAttribute('data-theme', 'light');
    } else {
      // system — ничего не ставим, работает через prefers-color-scheme
      document.body.removeAttribute('data-theme');
    }
  }, [theme]);

  return [theme, setTheme];
}