import React, { useRef, useMemo, useState } from 'react';
import { YMaps, Map, Placemark, ZoomControl, FullscreenControl } from '@pbe/react-yandex-maps';
import '../styles/FullMap.css';

// Константы вынесены за пределы компонента для стабильности
const API_KEY = '686e5b6d-df4e-49de-a918-317aa589c34c';
const MAP_QUERY = {
    apikey: API_KEY,
    lang: 'ru_RU',
    load: 'package.full' // Загружаем полный пакет сразу
};

const DEFAULT_CENTER = [64.5401, 40.5433];
const DEFAULT_ZOOM = 10;

export default function FullMap({ news }) {
    const mapRef = useRef(null);
    const ymapsRef = useRef(null);
    const [displayCount, setDisplayCount] = useState(5);

    // Подготовка данных: фильтрация и сортировка всех новостей с гео
    const allActiveNews = useMemo(() => {
        if (!Array.isArray(news)) return [];
        return news
            .filter(item => item && item.coords && Array.isArray(item.coords))
            .sort((a, b) => new Date(b.date) - new Date(a.date))
    }, [news]);

    const activeNews = useMemo(() => {
        return allActiveNews.slice(0, displayCount);
    }, [allActiveNews, displayCount]);

    // Обработчик загрузки API
    const handleApiLoad = (ymaps) => {
        ymapsRef.current = ymaps;
    };

    // Функция перелета к точке
    const flyTo = (coords) => {
        if (mapRef.current) {
            mapRef.current.setCenter(coords, 14, {
                duration: 1000,
                timingFunction: 'ease-in-out'
            });
        }
    };

    return (
        <div className="full-map-container">
            <div className="full-map-layout">
                {/* Левая часть: Карта */}
                <div className="full-map-wrapper">
                    <YMaps query={MAP_QUERY}>
                        <Map
                            defaultState={{
                                center: activeNews.length > 0 ? activeNews[0].coords : DEFAULT_CENTER,
                                zoom: DEFAULT_ZOOM,
                                controls: [] // Отключаем дефолтные контролы, добавим свои
                            }}
                            width="100%"
                            height="100%"
                            instanceRef={mapRef}
                            onLoad={handleApiLoad}
                        >
                            <ZoomControl options={{ float: 'right' }} />
                            <FullscreenControl />

                            {activeNews.map(item => (
                                <Placemark
                                    key={item.id}
                                    geometry={item.coords}
                                    properties={{
                                        // Красивая всплывающая карточка при наведении, завязанная на CSS переменные темы
                                        hintContent: `
                                            <div style="width: 420px; padding: 14px; background: var(--bg-card); border-radius: 16px; font-family: 'Inter', sans-serif; white-space: normal; overflow-wrap: break-word; box-sizing: border-box; box-shadow: 0 8px 24px rgba(0,0,0,0.2); border: 1px solid var(--border);">
                                                ${item.image ? `<img src="${item.image}" style="width: 100%; height: 220px; object-fit: cover; border-radius: 12px; margin-bottom: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.15);" />` : ''}
                                                <div style="font-weight: 700; font-size: 16px; line-height: 1.4; color: var(--text-primary); margin-bottom: 2px; word-break: break-word;">
                                                    ${item.title}
                                                </div>
                                            </div>
                                        `
                                    }}
                                    options={{
                                        preset: 'islands#lightBlueCircleDotIcon',
                                        hintOpenTimeout: 100 // Чтобы быстрее появлялось
                                    }}
                                    onClick={() => {
                                        window.location.hash = `#/news/${item.id}`;
                                    }}
                                />
                            ))}
                        </Map>
                    </YMaps>
                </div>

                {/* Правая часть: Список событий (Стиль MiniNewsSidebar) */}
                <div className="map-mini-sidebar">
                    <h3 className="sidebar-title">Лента событий</h3>
                    <div className="mini-news-list">
                        {activeNews.length > 0 ? (
                            activeNews.map(item => (
                                <div
                                    key={item.id}
                                    className="mini-news-card"
                                    onClick={() => flyTo(item.coords)}
                                >
                                    <div className="mini-news-meta">
                                        <span className="mini-news-date">{new Date(item.date).toLocaleDateString()}</span>
                                        <span className="mini-news-category">{item.category}</span>
                                    </div>
                                    <h4 className="mini-news-title">{item.title}</h4>
                                    {/* Кнопка "Читать далее" удалена по запросу */}
                                </div>
                            ))
                        ) : (
                            <div className="map-loading-state">
                                <p>Нет событий с координатами</p>
                            </div>
                        )}
                        {/* Кнопка загрузки старых новостей */}
                        {allActiveNews.length > displayCount && (
                            <button 
                                className="map-read-more-btn" 
                                style={{ marginTop: '10px' }}
                                onClick={() => setDisplayCount(prev => prev + 5)}
                            >
                                Показать ещё
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
