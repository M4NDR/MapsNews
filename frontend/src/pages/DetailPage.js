// src/pages/DetailPage.jsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import DOMPurify from 'dompurify';
import MapSidebar from '../components/MapSidebar';
import MiniNewsSidebar from '../components/MiniNewsSidebar';
import ErrorBoundary from '../components/ErrorBoundary';
import { fetchNewsDetail, fetchNews } from '../api';
import '../styles/DetailPage.css';

const DEFAULT_COORDS = [64.5401, 40.5433]; // Архангельск

export default function DetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [newsItem, setNewsItem] = useState(null);
  const [latestNews, setLatestNews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [mapOpen, setMapOpen] = useState(false);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchNewsDetail(id);
        setNewsItem(data);
        if (data.coords) setMapOpen(true);

        // Загрузка последних новостей для сайдбара
        try {
          const newsList = await fetchNews(5);
          setLatestNews(newsList.items || newsList); // Адаптация под формат ответа
        } catch (e) {
          console.error("Failed to load latest news", e);
        }
      } catch (err) {
        console.error(err);
        setError("Не удалось загрузить новость");
      } finally {
        setLoading(false);
      }
    };
    loadData();
    window.scrollTo(0, 0); // Скролл наверх
  }, [id]);

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
        <p>Загрузка новости...</p>
      </div>
    );
  }

  if (error || !newsItem) {
    return (
      <div className="error-container">
        <p>{error || "Новость не найдена"}</p>
        <button onClick={() => navigate(-1)} className="back-btn">Назад</button>
      </div>
    );
  }



  // Проверка валидности координат (массив из 2 чисел, не NaN)
  const isValidCoords = (c) => Array.isArray(c) && c.length === 2 && Number.isFinite(c[0]) && Number.isFinite(c[1]);
  const hasCoords = isValidCoords(newsItem.coords);
  const mapCoords = hasCoords ? newsItem.coords : [64.5401, 40.5433]; // Fallback

  return (
    <div className={`detail-layout ${mapOpen && hasCoords ? 'map-open' : ''}`}>
      {/* ЛЕВАЯ ЧАСТЬ — КАРТА (Пустой блок для сетки, если нет координат) */}
      <div className="map-container">
        {hasCoords && (
          <ErrorBoundary fallback={<div className="map-error">Ошибка карты</div>}>
            <MapSidebar coords={mapCoords} isOpen={mapOpen} />
          </ErrorBoundary>
        )}
      </div>

      {/* ПРАВАЯ ЧАСТЬ — НОВОСТЬ */}
      <div className="news-container">

        {/* НАВИГАЦИЯ (СЛЕВА СВЕРХУ) */}
        <div className="nav-buttons">
          <button onClick={() => navigate(-1)} className="nav-btn back-btn">
            ← Назад
          </button>
          {hasCoords && (
            <button
              className={`nav-btn map-btn ${mapOpen ? 'active' : ''}`}
              onClick={() => setMapOpen(!mapOpen)}
            >
              {mapOpen ? 'Скрыть карту' : 'Показать на карте'}
            </button>
          )}

          <Link to="/" className="nav-site-logo">Новостные карты</Link>
        </div>

        <div className="detail-wrapper">
          {/* БЛОК 1: ЗАГОЛОВОК И МЕТА */}
          <header className="news-header-block">
            <div className="header-content">
              <div className="news-meta-top">
                <span className="news-date">{newsItem.date}</span>
                {newsItem.category && <span className="news-category-tag">{newsItem.category}</span>}
              </div>
              <h1 className="news-title-main">{newsItem.title}</h1>
              <p className="news-source">Источник: {newsItem.source}</p>
            </div>

            {newsItem.image ? (
              <div className="news-hero-image" style={{ backgroundImage: `url(${newsItem.image})` }} />
            ) : (
              <div className="news-hero-pattern" />
            )}
          </header>

          {/* БЛОК 2: ОСНОВНОЙ ТЕКСТ */}
          <article className="news-content-block">
            <div
              className="detail-content"
              dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(newsItem.content) }}
            />

          </article>
        </div>

      </div>

      {/* ПРАВАЯ ЧАСТЬ - САЙДБАР С НОВОСТЯМИ */}
      <div className="sidebar-container">
        <MiniNewsSidebar news={latestNews} />
      </div>

    </div>
  );
}