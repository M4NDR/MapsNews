// src/components/CategoryTabs.jsx
import React from 'react';
import { useSearchParams } from 'react-router-dom';
import '../styles/CategoryTabs.css';

const CATEGORIES = ["все", "на карте", "дтп", "политика", "общество", "экономика", "спорт", "культура", "происшествия", "другое"];

export default function CategoryTabs() {
  const [searchParams, setSearchParams] = useSearchParams();
  const category = searchParams.get("category") || "все";

  return (
    <div className="category-tabs">
      {CATEGORIES.map(cat => (
        <button
          key={cat}
          className={`tab-btn ${category === cat ? 'active' : ''}`}
          onClick={() => setSearchParams({ category: cat })}
        >
          {cat === "все" ? "Все" : cat}
        </button>
      ))}
    </div>
  );
}