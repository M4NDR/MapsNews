// src/components/MapSidebar.jsx
import React from 'react';
import { YMaps, Map, Placemark } from '@pbe/react-yandex-maps';
import '../styles/MapSidebar.css';

const YANDEX_API_KEY = '686e5b6d-df4e-49de-a918-317aa589c34c';

export default function MapSidebar({ coords, isOpen }) {
  return (
    <div className="map-wrapper">
      <div className={`map-sidebar ${isOpen ? 'open' : ''}`}>
        <YMaps query={{ apikey: YANDEX_API_KEY, lang: 'ru_RU' }}>
          <Map
            key={coords.join(',')} /* Форсируем перерисовку при смене координат */
            defaultState={{ center: coords, zoom: 14 }}
            state={{ center: coords, zoom: 14 }}
            width="100%"
            height="100%"
          >
            {coords && <Placemark geometry={coords} options={{ preset: 'islands#redDotIcon' }} />}
          </Map>
        </YMaps>
      </div>
    </div>
  );
}