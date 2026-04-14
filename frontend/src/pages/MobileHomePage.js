import React from 'react';
import NewsList from '../components/NewsList';
import CategoryTabs from '../components/CategoryTabs';
import SearchInput from '../components/SearchInput';
import ThemeToggle from '../components/ThemeToggle';
import WeatherWidget from '../components/WeatherWidget';
import FullMap from '../components/FullMap';
import '../styles/MobileHomePage.css';

export default function MobileHomePage({
    allNews,
    displayedNews,
    loading,
    hasMore,
    loadMore,
    category,
    search,
    setSearch,
    onlyWithCoords,
    setOnlyWithCoords
}) {
    return (
        <div className="mobile-home-container">
            <header className="mobile-navbar">
                <div className="mobile-nav-top">
                    <h1 className="mobile-logo">Map-News</h1>
                    <ThemeToggle />
                </div>

                <div className="mobile-search-wrapper">
                    <SearchInput value={search} onChange={setSearch} />
                </div>

                <div className="mobile-filters">
                    <CategoryTabs hideMap={true} />
                </div>
            </header>

            <main className="mobile-content">
                {category === "на карте" ? (
                    <div className="mobile-map-view">
                        <FullMap news={allNews} />
                    </div>
                ) : (
                    <div className="mobile-news-feed">
                        <NewsList
                            news={displayedNews}
                            loading={loading}
                            hasMore={hasMore}
                            onLoadMore={loadMore}
                            category={category}
                        />
                    </div>
                )}
            </main>

            {/* Плавающая кнопка фильтра с координатами (находится слева-внизу) */}
            {category !== "на карте" && (
                <button 
                    className={`floating-geomark-btn ${onlyWithCoords ? 'active' : ''}`}
                    onClick={() => setOnlyWithCoords(!onlyWithCoords)}
                >
                    {onlyWithCoords ? '🎯 Сбросить фильтр геометок' : '🌍 Только с геометкой'}
                </button>
            )}
        </div>
    );
}
