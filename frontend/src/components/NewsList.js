// src/components/NewsList.jsx
// src/components/NewsList.jsx
import React from 'react';
import NewsCard from './NewsCard';
import SkeletonCard from './SkeletonCard';
import '../styles/NewsList.css';

export default function NewsList({ news, loading, hasMore, onLoadMore, category }) {
  if (news.length === 0 && loading) {
    return (
      <div className="news-list" key="loading">
        {Array(6).fill().map((_, i) => <SkeletonCard key={i} />)}
      </div>
    );
  }

  return (
    <div className="news-list" key={category}>
      {news.map((item) => (
        <div key={item.id}>
          <NewsCard item={item} />
        </div>
      ))}

      {hasMore && (
        <button className="load-more-btn" onClick={onLoadMore} disabled={loading}>
          {loading ? 'Загрузка...' : 'Больше новостей'}
        </button>
      )}

      {!hasMore && news.length > 0 && (
        <p className="no-more-news">Это все новости</p>
      )}

      {!hasMore && news.length === 0 && !loading && (
        <p className="no-more-news">Новости не найдены</p>
      )}
    </div>
  );
}