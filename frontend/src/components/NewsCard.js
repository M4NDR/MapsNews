// src/components/NewsCard.jsx
import React from 'react';
import { Link } from 'react-router-dom';
import '../styles/NewsCard.css';

export default function NewsCard({ item }) {
  return (
    <Link to={`/news/${item.id}`} className="news-card-link">
      <article className="news-card">
        {item.image ? (
          <img src={item.image} alt={item.title} className="news-card-image" />
        ) : (
          <div className="no-image-card">Нет фото</div>
        )}
        <div className="news-content">
          <h3 className="news-title">{item.title}</h3>
          <p className="news-preview">{item.preview}</p>
          <div className="news-footer">
            <small className="news-meta">{item.date}</small>
            <span className="news-category">{item.category}</span>
          </div>
        </div>
      </article>
    </Link>
  );
}