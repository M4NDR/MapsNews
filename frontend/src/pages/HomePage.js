import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import NewsList from '../components/NewsList';
import CategoryTabs from '../components/CategoryTabs';
import SearchInput from '../components/SearchInput';
import ThemeToggle from '../components/ThemeToggle';
import WeatherWidget from '../components/WeatherWidget';
import FullMap from '../components/FullMap';
import MobileHomePage from './MobileHomePage'; // Импорт новой версии
import { fetchNews } from '../api';
import '../styles/HomePage.css';

export default function HomePage() {
  const [allNews, setAllNews] = useState([]);
  const [displayedNews, setDisplayedNews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [page, setPage] = useState(1);
  const [searchParams] = useSearchParams();
  const category = searchParams.get("category") || "все";
  const [search, setSearch] = useState("");

  // Определение мобильного экрана
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const ITEMS_PER_PAGE = 20;

  // Загрузка всех новостей один раз при старте
  useEffect(() => {
    const fetchFreshNews = async () => {
      try {
        const data = await fetchNews(500);
        setAllNews(data);
        sessionStorage.setItem('preloaded_news', JSON.stringify(data));
      } catch (err) {
        console.error("Ошибка загрузки новостей:", err);
      }
    };

    const initData = async () => {
      const cachedNews = sessionStorage.getItem('preloaded_news');
      if (cachedNews) {
        try {
          const parsed = JSON.parse(cachedNews);
          setAllNews(parsed);
          setTimeout(fetchFreshNews, 2000);
          return;
        } catch (e) {
          console.error("Ошибка парсинга кэша:", e);
        }
      }

      setLoading(true);
      await fetchFreshNews();
      setLoading(false);
    };

    initData();
  }, []);

  // Фильтрация и пагинация
  useEffect(() => {
    let filtered = [...allNews];

    if (category === "на карте") {
      filtered = filtered.filter(item => item && item.coords);
    } else if (category && category !== "все") {
      filtered = filtered.filter(item =>
        item && item.category && item.category.toLowerCase() === category.toLowerCase()
      );
    }

    if (search) {
      const lowerSearch = search.toLowerCase();
      filtered = filtered.filter(item =>
        item.title.toLowerCase().includes(lowerSearch) ||
        (item.preview && item.preview.toLowerCase().includes(lowerSearch))
      );
    }

    const endIndex = page * ITEMS_PER_PAGE;
    setDisplayedNews(filtered.slice(0, endIndex));
    setHasMore(endIndex < filtered.length);
  }, [allNews, search, page, category]);

  const loadMore = () => {
    setPage(prev => prev + 1);
  };

  // ЕСЛИ МОБИЛЬНЫЙ — ПОКАЗЫВАЕМ ОТДЕЛЬНУЮ СТРАНИЦУ
  if (isMobile) {
    return (
      <MobileHomePage
        allNews={allNews}
        displayedNews={displayedNews}
        loading={loading}
        hasMore={hasMore}
        loadMore={loadMore}
        category={category}
        search={search}
        setSearch={setSearch}
      />
    );
  }

  // ДЕКСТОПНАЯ ВЕРСИЯ (без изменений)
  return (
    <>
      <header className="header">
        <h1>Новостные Карты</h1>
        <div className="header-controls">
          <SearchInput value={search} onChange={setSearch} />
          <WeatherWidget />
          <CategoryTabs />
          <ThemeToggle />
        </div>
      </header>
      {category === "на карте" ? (
        <div className="full-map-container">
          <FullMap news={allNews} />
        </div>
      ) : (
        <div className="home-page">
          <NewsList
            news={displayedNews}
            loading={loading}
            hasMore={hasMore}
            onLoadMore={loadMore}
            category={category}
          />
        </div>
      )}
    </>
  );
}