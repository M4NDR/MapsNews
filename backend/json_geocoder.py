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
    def __init__(self, db_path: str = STREETS_DB_PATH):
        self.streets = self._load_streets(db_path)
        # Сортируем улицы по длине (от длинных к коротким) для правильного поиска
        self.streets.sort(key=len, reverse=True)
        
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
        - "ленина, 15а" → "15а"
        """
        text_lower = text.lower()
        
        # Находим позицию улицы
        street_pos = text_lower.find(street)
        if street_pos == -1:
            return None
        
        # Берем текст после улицы (макс 80 символов)
        text_after = text_lower[street_pos + len(street):street_pos + len(street) + 80]
        
        # Паттерны для поиска номера дома
        patterns = [
            r'[,\s]+(?:дом|д\.?|дома)\s*(\d+[а-я]?(?:/\d+)?)',  # ", дом 5" или ", д. 10а" или "д. 5/1"
            r'[,\s]+(\d+[а-я]?(?:/\d+)?)',                      # ", 5" или " 10а" или "5/1"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_after)
            if match:
                number = match.group(1)
                logger.info(f"[НОМЕР] Дом: {number}")
                return number
        
        return None
    
    def geocode_with_yandex(self, address: str) -> Optional[List[float]]:
        """
        Геокодирует адрес через Yandex API.
        Возвращает [lat, lon] или None.
        """
        if not address:
            return None
        
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
        
        Args:
            title: Заголовок новости
            content: Текст новости
            
        Returns:
            tuple: (address: str | None, coords: [lat, lon] | None)
        """
        full_text = f"{title} {content}"
        
        # 1. Ищем улицу
        street = self.find_street_in_text(full_text)
        if not street:
            logger.info("[РЕЗУЛЬТАТ] ❌ Улица не найдена")
            return None, None
        
        # 2. Ищем номер дома
        building = self.extract_building_number(full_text, street)
        
        # 3. Формируем адрес
        if building:
            address = f"Архангельск, {street}, {building}"
        else:
            address = f"Архангельск, {street}"
        
        logger.info(f"[АДРЕС] {address}")
        
        # 4. Геокодируем
        coords = self.geocode_with_yandex(address)
        
        return address, coords


# === ТЕСТИРОВАНИЕ ===
if __name__ == "__main__":
    geocoder = SimpleGeocoder()
    
    print(f"\n{'='*60}")
    print(f"ТЕСТИРОВАНИЕ ГЕОКОДЕРА")
    print(f"Загружено улиц: {len(geocoder.streets)}")
    print(f"{'='*60}\n")
    
    # Тестовые примеры
    test_cases = [
        ("ДТП на Ленина", "Сегодня утром на улице Ленина, дом 5 произошло столкновение двух автомобилей."),
        ("Пожар на Троицком", "На проспекте Троицкий возле дома 55 произошло возгорание."),
        ("Авария на Ломоносова", "Проспект Ломоносова, 202 будет закрыт на ремонт."),
        ("ДТП на Воскресенской", "На Воскресенской улице, 20 сбили пешехода."),
        ("Ремонт на Победы", "Улица Победы перекрыта для ремонта."),
        ("Событие на площади", "На площади Ленина прошел митинг."),
    ]
    
    for i, (title, content) in enumerate(test_cases, 1):
        print(f"\n{'─'*60}")
        print(f"ТЕСТ #{i}")
        print(f"{'─'*60}")
        print(f"📰 Заголовок: {title}")
        print(f"📝 Текст: {content[:60]}...")
        print()
        
        address, coords = geocoder.process_text(title, content)
        
        if address:
            print(f"✅ АДРЕС: {address}")
            if coords:
                print(f"📍 КООРДИНАТЫ: {coords}")
            else:
                print(f"❌ Координаты не получены")
        else:
            print(f"❌ Адрес не распознан")
    
    print(f"\n{'='*60}\n")
