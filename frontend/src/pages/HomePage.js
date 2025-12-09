// src/pages/HomePage.jsx
import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import NewsList from '../components/NewsList';
import CategoryTabs from '../components/CategoryTabs';
import SearchInput from '../components/SearchInput';
import ThemeToggle from '../components/ThemeToggle';
import WeatherWidget from '../components/WeatherWidget';
import { fetchNews } from '../api';
import '../styles/HomePage.css';

export default function HomePage() {
  const [allNews, setAllNews] = useState([]); // Все загруженные новости
  const [displayedNews, setDisplayedNews] = useState([]); // Отображаемые новости
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [page, setPage] = useState(1);
  const [searchParams] = useSearchParams();
  const category = searchParams.get("category") || "все";
  const [search, setSearch] = useState("");

  const ITEMS_PER_PAGE = 20;

  // Загрузка всех новостей при смене категории
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const data = await fetchNews(200, category);
        setAllNews(data);
        setPage(1);
        setHasMore(true);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [category]);

  // Фильтрация и пагинация
  useEffect(() => {
    let filtered = allNews;

    // Фильтр по категории "на карте"
    if (category === "на карте") {
      filtered = filtered.filter(item => item.coords);
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

  return (
    <>
      <header
        className="header"
        style={{
          backgroundImage: `linear-gradient(rgba(0, 0, 0, 0.6), rgba(0, 0, 0, 0.6)), url(/Arkh.jpg)`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundAttachment: 'scroll', // Fixed конфликтует с border-radius на некоторых браузерах/контейнерах, лучше scroll или local для карточки
          borderRadius: '40px'
        }}
      >
        <h1>MapsNews</h1>
        <div className="header-controls">
          <SearchInput value={search} onChange={setSearch} />
          <WeatherWidget />
          <CategoryTabs />
          <ThemeToggle />
        </div>
      </header>
      <div className="home-page">
        <NewsList news={displayedNews} loading={loading} hasMore={hasMore} onLoadMore={loadMore} />
      </div>
    </>
  );
}