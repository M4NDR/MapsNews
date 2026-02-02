import React, { useState, useEffect } from 'react';
import '../styles/WeatherWidget.css';

const WEATHER_CODES = {
    0: 'Ясно',
    1: 'Преимущественно ясно',
    2: 'Переменная облачность',
    3: 'Пасмурно',
    45: 'Туман',
    48: 'Туман',
    51: 'Морось', 53: 'Морось', 55: 'Плотная морось',
    61: 'Слабый дождь', 63: 'Дождь', 65: 'Сильный дождь',
    71: 'Слабый снег', 73: 'Снег', 75: 'Сильный снег',
    77: 'Снежные зерна',
    80: 'Ливень', 81: 'Сильный ливень', 82: 'Очень сильный ливень',
    85: 'Снегопад', 86: 'Сильный снегопад',
    95: 'Гроза',
    96: 'Гроза с градом', 99: 'Гроза с сильным градом'
};

export default function WeatherWidget() {
    const [weather, setWeather] = useState(null);
    const [time, setTime] = useState(new Date());

    // Обновление времени каждую секунду
    useEffect(() => {
        const timer = setInterval(() => {
            setTime(new Date());
        }, 1000);
        return () => clearInterval(timer);
    }, []);

    // Получение погоды
    useEffect(() => {
        const fetchWeather = async () => {
            try {
                const res = await fetch(
                    "https://api.open-meteo.com/v1/forecast?latitude=64.54&longitude=40.54&current_weather=true&timezone=Europe%2FMoscow"
                );
                const data = await res.json();
                setWeather(data.current_weather);
            } catch (e) {
                console.error("Ошибка загрузки погоды:", e);
            }
        };

        
        fetchWeather();
        // Обновлять погоду каждые 15 минут
        const interval = setInterval(fetchWeather, 900000);
        return () => clearInterval(interval);
    }, []);

    // Форматирование времени для Архангельска (UTC+3, то есть MSK)
    const formattedTime = time.toLocaleTimeString('ru-RU', {
        timeZone: 'Europe/Moscow',
        hour: '2-digit',
        minute: '2-digit'
    });

    const formattedDate = time.toLocaleDateString('ru-RU', {
        timeZone: 'Europe/Moscow',
        day: 'numeric',
        month: 'long',
        weekday: 'short'
    });

    return (
        <div className="weather-widget">
            <div className="weather-info">
                {weather ? (
                    <>
                        <span className="temp">{Math.round(weather.temperature)}°C</span>
                        <span className="condition">{WEATHER_CODES[weather.weathercode] || 'Нет данных'}</span>
                    </>
                ) : (
                    <span>Загрузка...</span>
                )}
            </div>
            <div className="time-info">
                <div className="current-time">{formattedTime}</div>
                <div className="current-date">{formattedDate}</div>
            </div>
        </div>
    );
}
