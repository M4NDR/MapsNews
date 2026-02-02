import React, { useRef, useMemo } from 'react';
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

    // Подготовка данных: фильтрация и сортировка
    const activeNews = useMemo(() => {
        if (!Array.isArray(news)) return [];
        return news
            .filter(item => item && item.coords && Array.isArray(item.coords))
            .sort((a, b) => new Date(b.date) - new Date(a.date))
            .slice(0, 5); // Оставляем только 5 последних
    }, [news]);

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
                                        // Убираем описание, оставляем только маркер
                                        hintContent: item.title
                                    }}
                                    options={{
                                        preset: 'islands#lightBlueCircleDotIcon' // Голубоватый цвет
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
                                    <button
                                        className="map-read-more-btn"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            window.location.hash = `#/news/${item.id}`;
                                        }}
                                    >
                                        Читать далее
                                    </button>
                                </div>
                            ))
                        ) : (
                            <div className="map-loading-state">
                                <p>Нет событий с координатами</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
