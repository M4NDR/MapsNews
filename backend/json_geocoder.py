"""
Простой геокодер на основе JSON-справочника улиц.
Алгоритм:
1. Ищет улицу из JSON в тексте новости
2. Извлекает номер дома (если есть)
3. Формирует адрес "Архангельск, улица, номер"
4. Отправляет в Yandex API для получения координат
"""

import os
import json
import requests
import re
import logging
from typing import Optional, List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEOCODER_API_KEY = os.getenv("GEOCODER_API_KEY", "686e5b6d-df4e-49de-a918-317aa589c34c")
ARKH_OBLAST_BBOX = "35.5,62.8~49.0,67.5"
STREETS_DB_PATH = "streets_database.json"


class SimpleGeocoder:
    def __init__(self, db_path: str = STREETS_DB_PATH, cache_path: str = "geo_cache.json"):
        self.streets = self._load_streets(db_path)
        self.streets.sort(key=len, reverse=True)
        self.cache_path = cache_path
        self.cache = self._load_cache()

    def _load_cache(self) -> dict:
        """Загружает кэш координат из файла"""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_cache(self):
        """Сохраняет кэш в файл"""
        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[CACHE] Ошибка сохранения: {e}")

    def _load_streets(self, db_path: str) -> List[str]:
        """Загружает список улиц из JSON"""
        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("streets", [])
        except Exception as e:
            logger.error(f"[JSON] Ошибка загрузки: {e}")
            return []
    
    def find_street_in_text(self, text: str) -> Optional[str]:
        """
        Ищет первую найденную улицу из справочника в тексте.
        Возвращает название улицы или None.
        """
        text_lower = text.lower()
        
        for street in self.streets:
            # Используем поиск с границами слов, чтобы избежать частичных совпадений
            # Например, чтобы "ул. Садовая" не нашлась внутри "ул. Садовая-Кудринская" (если такой нет в базе)
            # Но для простоты пока оставим обычный find, так как база отсортирована по длине
            if street in text_lower:
                logger.info(f"[НАЙДЕНО] Улица: {street}")
                return street
        
        return None
    
    def extract_building_number(self, text: str, street: str) -> Optional[str]:
        """
        Извлекает номер дома после названия улицы.
        Примеры: 
        - "улица ленина 5" → "5"
        - "ул. ленина, д. 10" → "10"
        - "ленина-15а" → "15а"
        """
        text_lower = text.lower()
        street_pos = text_lower.find(street)
        if street_pos == -1: return None
        
        # Текст после улицы (увеличим окно до 20 символов, т.к. номер обычно близко)
        text_after = text_lower[street_pos + len(street):]
        # Берем только начало строки, до первой точки или конца предложения, но не слишком много
        # Regex search сам найдет нужное в начале строки
        
        # Паттерны для поиска номера дома
        # 1. С явным указателем "дом/д."
        # 2. Через дефис (Ленина-5)
        # 3. Просто число после запятой или пробела, но фильтруем года (19xx, 20xx)
        
        patterns = [
            r'[,\s]+(?:дом|д\.?|дома)\s*(\d+[а-я]?(?:[/\-]\d+)?)',  # "д. 5", "дом 10а", "д.5/1"
            r'[ \t]*-[ \t]*(\d+[а-я]?(?:[/\-]\d+)?)',               # "Ленина-5"
            r'[,\s]+(\d+[а-я]?(?:[/\-]\d+)?)'                       # ", 5", " 10а"
        ]
        
        for pattern in patterns:
            # Ищем только в начале text_after (до 20 символов)
            snippet = text_after[:20]
            match = re.match(pattern, snippet) # Используем match, чтобы искать от начала фрагмента
            if match:
                number = match.group(1)
                
                # Фильтр годов (1900-2099), если число простое (без букв и дробей)
                if number.isdigit() and 1900 <= int(number) <= 2099:
                    continue
                    
                logger.info(f"[НОМЕР] Дом: {number}")
                return number
        
        return None
    
    def geocode_with_yandex(self, address: str) -> Optional[List[float]]:
        """
        Геокодирует адрес через Yandex API с кэшированием.
        """
        if not address: return None
        
        # 1. Проверяем кэш
        if address in self.cache:
            logger.info(f"[CACHE] ✅ Найдено: {address}")
            return self.cache[address]
        
        try:
            url = (
                f"https://geocode-maps.yandex.ru/1.x/?apikey={GEOCODER_API_KEY}"
                f"&geocode={requests.utils.quote(address)}&format=json&results=1"
                f"&bbox={ARKH_OBLAST_BBOX}&rspn=1"
            )
            
            logger.info(f"[YANDEX] Запрос: {address}")
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                members = data["response"]["GeoObjectCollection"]["featureMember"]
                
                if members:
                    pos = members[0]["GeoObject"]["Point"]["pos"]
                    lon, lat = map(float, pos.split())
                    coords = [lat, lon]
                    
                    # Сохраняем в кэш
                    self.cache[address] = coords
                    self._save_cache()
                    
                    logger.info(f"[YANDEX] ✅ Координаты: {coords}")
                    return coords
                else:
                    logger.info(f"[YANDEX] ❌ Адрес не найден")
            else:
                logger.error(f"[YANDEX] ❌ HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"[YANDEX] ❌ Ошибка: {e}")
        
        return None
    
    def process_text(self, title: str, content: str) -> Tuple[Optional[str], Optional[List[float]]]:
        """
        Обрабатывает текст новости и возвращает (адрес, координаты).
        """
        full_text = f"{title} {content}"
        
        street = self.find_street_in_text(full_text)
        if not street:
            return None, None
        
        building = self.extract_building_number(full_text, street)
        
        if building:
            address = f"Архангельск, {street}, {building}"
        else:
            address = f"Архангельск, {street}"
        
        coords = self.geocode_with_yandex(address)
        
        return address, coords


# === ТЕСТИРОВАНИЕ ===
