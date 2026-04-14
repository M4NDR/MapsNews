// src/components/SearchInput.jsx
import React from 'react';
import '../styles/SearchInput.css';

export default function SearchInput({ value, onChange }) {
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && value.trim().toUpperCase() === 'ZOV') {
      window.location.href = "https://northernzovstudio.c6t.ru/";
    }
  };

  return (
    <input
      type="text"
      placeholder="Поиск по заголовкам..."
      value={value}
      onChange={e => onChange(e.target.value)}
      onKeyDown={handleKeyDown}
      className="search-input"
    />
  );
}