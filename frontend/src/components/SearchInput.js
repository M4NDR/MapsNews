// src/components/SearchInput.jsx
import React from 'react';
import '../styles/SearchInput.css';

export default function SearchInput({ value, onChange }) {
  return (
    <input
      type="text"
      placeholder="Поиск по заголовкам..."
      value={value}
      onChange={e => onChange(e.target.value)}
      className="search-input"
    />
  );
}