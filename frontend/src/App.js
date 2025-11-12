// frontend/src/App.js
import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Routes,
  Route,
  Link,
  useParams,
  useNavigate,
  useSearchParams
} from 'react-router-dom';
import DOMPurify from 'dompurify';
import { YMaps, Map, Placemark } from '@pbe/react-yandex-maps';
import './App.css';

const YANDEX_API_KEY = '686e5b6d-df4e-49de-a918-317aa589c34c';

const CATEGORIES = ["все", "дтп", "политика", "общество", "экономика", "спорт", "культура", "происшествия", "другое"];

function useDarkMode() {
  const [darkMode, setDarkMode] = useState(() => {
    return localStorage.getItem('darkMode') === 'true';
  });

  useEffect(() => {
    localStorage.setItem('darkMode', darkMode);
    document.body.classList.toggle('dark-mode', darkMode);
  }, [darkMode]);

  return [darkMode, setDarkMode];
}

// === ДЕТАЛЬНАЯ СТРАНИЦА С ДИНАМИЧЕСКОЙ КАРТОЙ ===
function NewsDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [newsItem, setNewsItem] = useState(null);
  const [fullContent, setFullContent] = useState("");
  const [fullImage, setFullImage] = useState("");
  const [coords, setCoords] = useState([64.5404, 40.5328]);
  const [loading, setLoading] = useState(true);
  const [showMap, setShowMap] = useState(false);
  const [darkMode, setDarkMode] = useDarkMode();

  useEffect(() => {
    const fetchFull = async () => {
      try {
        setLoading(true);
        const listRes = await fetch(`http://127.0.0.1:8000/news?limit=200`);
        const list = await listRes.json();
        const item = list.find(n => n.id === parseInt(id));
        setNewsItem(item);

        const res = await fetch(`http://127.0.0.1:8000/news/${id}/full`);
        const data = await res.json();
        setFullContent(data.content || "<p>Текст не найден</p>");
        setFullImage(item?.image || data.image || "");

        if (data.coords) {
          setCoords(data.coords);
          setShowMap(true);
        }
      } catch (err) {
        console.error("Ошибка:", err);
        setFullContent("<p>Ошибка загрузки</p>");
      } finally {
        setLoading(false);
      }
    };
    if (id) fetchFull();
  }, [id]);

  if (loading) return <div className="loading">Загрузка...</div>;

  return (
    <div className={`page-wrapper ${showMap ? 'map-open' : ''}`}>
      <button onClick={() => navigate(-1)} className="back-btn">
        Назад
      </button>

      <div className="detail-container">
        {showMap && (
          <div className="map-wrapper">
            <YMaps query={{ apikey: YANDEX_API_KEY, lang: 'ru_RU' }}>
              <Map state={{ center: coords, zoom: 15 }} width="100%" height="100%">
                <Placemark 
                  geometry={coords}
                  options={{
                    preset: 'islands#redDotIcon'
                  }}
                />
              </Map>
            </YMaps>
          </div>
        )}

        <div className="content-wrapper">
          <div className="map-toggle">
            <button
              className="map-btn"
              onClick={() => setShowMap(!showMap)}
            >
              {showMap ? 'Скрыть карту' : 'Показать на карте'}
            </button>
          </div>

          <div className="detail-card">
            <div className="detail-header">
              <h1>{newsItem?.title || "Загрузка..."}</h1>
              <p className="detail-meta">
                {newsItem?.date} — {newsItem?.source}
                {newsItem?.category && ` — ${newsItem.category}`}
              </p>
            </div>

            {fullImage ? (
              <img src={fullImage} alt={newsItem?.title} className="detail-image" />
            ) : (
              <div className="no-image">Фото отсутствует</div>
            )}

            <div
              className="detail-content"
              dangerouslySetInnerHTML={{
                __html: DOMPurify.sanitize(fullContent)
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

// === СПИСОК НОВОСТЕЙ С БЕСКОНЕЧНЫМ СКРОЛЛОМ И ПОИСКОМ ===
function NewsList() {
  const [news, setNews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [searchParams, setSearchParams] = useSearchParams();
  const category = searchParams.get("category") || "все";
  const [search, setSearch] = useState("");
  const [darkMode, setDarkMode] = useDarkMode();
  const observer = useRef();

  const lastNewsRef = useCallback(node => {
    if (loading) return;
    if (observer.current) observer.current.disconnect();
    observer.current = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting && hasMore) {
        loadMore();
      }
    });
    if (node) observer.current.observe(node);
  }, [loading, hasMore]);

  const loadMore = async () => {
    if (loading) return;
    setLoading(true);
    try {
      let url = `http://127.0.0.1:8000/news?limit=200`;
      if (category && category !== "все") url += `&category=${category}`;
      const res = await fetch(url);
      const data = await res.json();

      const filtered = data.filter(item =>
        item.title.toLowerCase().includes(search.toLowerCase())
      );

      setNews(prev => {
        const start = prev.length;
        const newItems = filtered.slice(start, start + 20);
        setHasMore(start + newItems.length < filtered.length);
        return [...prev, ...newItems];
      });
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setNews([]);
    setHasMore(true);
    loadMore();
  }, [category, search]);

  return (
    <div className="page-wrapper">
      <header className="header">
        <h1>MapsNews</h1>

        <div className="header-controls">
          <input
            type="text"
            placeholder="Поиск по заголовкам..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="search-input"
          />

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

          <button
            className="theme-toggle"
            onClick={() => setDarkMode(!darkMode)}
          >
            {darkMode ? 'Светлая' : 'Тёмная'}
          </button>
        </div>
      </header>

      <div className="news-list">
        {news.length === 0 && loading && (
          Array(6).fill().map((_, i) => (
            <div className="news-card skeleton-card" key={i}>
              <div className="skeleton skeleton-image"></div>
              <div className="news-content">
                <div className="skeleton skeleton-title"></div>
                <div className="skeleton skeleton-text"></div>
                <div className="skeleton skeleton-text" style={{width: '60%'}}></div>
              </div>
            </div>
          ))
        )}

        {news.map((item, index) => (
          <Link
            to={`/news/${item.id}`}
            key={item.id}
            className="news-card-link"
            ref={index === news.length - 5 ? lastNewsRef : null}
          >
            <div className="news-card">
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
            </div>
          </Link>
        ))}

        {loading && news.length > 0 && (
          <div className="loading">Подгружаем ещё новости...</div>
        )}
        {!hasMore && news.length > 0 && (
          <div className="loading">Это все новости в категории «{category}»</div>
        )}
      </div>
    </div>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<NewsList />} />
      <Route path="/news/:id" element={<NewsDetail />} />
    </Routes>
  );
}

export default App;