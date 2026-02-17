"""
Улучшенный геокодер с использованием NLP (Natasha).

Архитектура:
1. Извлекает адрес через Natasha AddrExtractor
2. Fallback: regex для простых случаев
3. Геокодирование через Yandex API с указанием региона
4. Проверка, что результат из Архангельской области
5. Кэширование для экономии API-запросов
"""

import os
import json
import requests
import re
import logging
from typing import Optional, List, Tuple
from natasha import Segmenter, MorphVocab, AddrExtractor, Doc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEOCODER_API_KEY = os.getenv("GEOCODER_API_KEY", "686e5b6d-df4e-49de-a918-317aa589c34c")


class ImprovedGeocoder:
    def __init__(self, cache_path: str = "geo_cache.json"):
        """Инициализация геокодера с Natasha и кэшем"""
        self.cache_path = cache_path
        self.cache = self._load_cache()
        
        # Инициализация Natasha
        self.segmenter = Segmenter()
        self.morph_vocab = MorphVocab()
        self.addr_extractor = AddrExtractor(self.morph_vocab)

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

    def extract_address_natasha(self, text: str) -> Optional[str]:
        """
        Извлекает адрес с помощью Natasha AddrExtractor.
        
        Преимущества:
        - Понимает падежи (на улице Ленина, улицы Ленина)
        - Извлекает структурированные данные
        - Не требует базы данных улиц
        """
        try:
            # Создаем документ и сегментируем
            doc = Doc(text)
            doc.segment(self.segmenter)
            
            # Извлекаем адреса
            matches = list(self.addr_extractor(doc.text))
            
            for match in matches:
                fact = match.fact
                parts = []
                
                # Собираем части адреса
                if hasattr(fact, 'street') and fact.street:
                    parts.append(fact.street)
                if hasattr(fact, 'building') and fact.building:
                    parts.append(f"д. {fact.building}")
                
                if parts:
                    address = ", ".join(parts)
                    logger.info(f"[NATASHA] Извлечен адрес: {address}")
                    return address
                    
        except Exception as e:
            logger.error(f"[NATASHA] Ошибка: {e}")
        
        return None

    def extract_address_regex(self, text: str) -> Optional[str]:
        """
        Fallback: извлечение адреса через regex.
        
        Используется, если Natasha не смогла найти адрес.
        Ищет паттерны вида: "улица/ул. Название [, дом X]"
        """
        patterns = [
            # "ул. Ленина, 5" или "улица Ленина, дом 10"
            r'(?:ул(?:ица)?\.?\s+)([А-ЯЁа-яё\-]+)(?:,?\s*(?:д(?:ом)?\.?\s*)?(\d+[а-я]?))?',
            # "проспект Ломоносова" или "пр. Троицкий"
            r'(?:пр(?:оспект)?\.?\s+)([А-ЯЁа-яё\-]+)(?:,?\s*(?:д(?:ом)?\.?\s*)?(\d+[а-я]?))?',
            # "площадь Ленина"
            r'(?:площадь|пл\.?\s+)([А-ЯЁа-яё\-]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                street = match.group(1)
                building = match.group(2) if len(match.groups()) > 1 else None
                
                if building:
                    address = f"{street}, д. {building}"
                else:
                    address = street
                    
                logger.info(f"[REGEX] Извлечен адрес: {address}")
                return address
        
        return None

    def geocode_with_yandex(self, address: str) -> Optional[List[float]]:
        """
        Геокодирует адрес через Yandex API с проверкой региона.
        
        Изменения:
        - Добавляем "Архангельская область" в запрос вместо bbox
        - Проверяем, что результат действительно из нужного региона
        """
        if not address:
            return None
        
        # Формируем полный запрос с регионом
        full_query = f"{address}, Архангельская область"
        
        # Проверяем кэш
        if full_query in self.cache:
            logger.info(f"[CACHE] ✅ {full_query}")
            return self.cache[full_query]
        
        try:
            url = (
                f"https://geocode-maps.yandex.ru/1.x/?apikey={GEOCODER_API_KEY}"
                f"&geocode={requests.utils.quote(full_query)}"
                f"&format=json&results=3"  # Берем несколько результатов для проверки
            )
            
            logger.info(f"[YANDEX] Запрос: {full_query}")
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                members = data["response"]["GeoObjectCollection"]["featureMember"]
                
                # Проверяем каждый результат
                for member in members:
                    geo_obj = member["GeoObject"]
                    
                    # Проверяем, что объект в Архангельской области
                    address_details = geo_obj.get("metaDataProperty", {}).get("GeocoderMetaData", {}).get("Address", {})
                    components = address_details.get("Components", [])
                    
                    # Ищем компонент "AdministrativeArea" (область)
                    is_arkhangelsk = False
                    for component in components:
                        if component.get("kind") == "province":
                            province_name = component.get("name", "").lower()
                            if "архангельск" in province_name:
                                is_arkhangelsk = True
                                break
                    
                    if is_arkhangelsk:
                        pos = geo_obj["Point"]["pos"]
                        lon, lat = map(float, pos.split())
                        coords = [lat, lon]
                        
                        # Сохраняем в кэш
                        self.cache[full_query] = coords
                        self._save_cache()
                        
                        logger.info(f"[YANDEX] ✅ Координаты: {coords}")
                        return coords
                
                logger.info(f"[YANDEX] ❌ Адрес не в Архангельской области")
            else:
                logger.error(f"[YANDEX] ❌ HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"[YANDEX] ❌ Ошибка: {e}")
        
        return None

    def process_text(self, title: str, content: str) -> Tuple[Optional[str], Optional[List[float]]]:
        """
        Обрабатывает текст новости и возвращает (адрес, координаты).
        
        Пайплайн:
        1. Natasha AddrExtractor
        2. Regex fallback
        3. Yandex геокодирование с проверкой региона
        """
        full_text = f"{title} {content}"
        
        # 1. Пробуем Natasha
        address = self.extract_address_natasha(full_text)
        
        # 2. Fallback: regex
        if not address:
            address = self.extract_address_regex(full_text)
        
        # 3. Если адрес не найден
        if not address:
            logger.info("[GEOCODER] ❌ Адрес не найден")
            return None, None
        
        # 4. Геокодируем
        coords = self.geocode_with_yandex(address)
        
        return address, coords


# Для обратной совместимости с main.py
class SimpleGeocoder(ImprovedGeocoder):
    """Алиас для обратной совместимости"""
    pass


# === ТЕСТИРОВАНИЕ ===
if __name__ == "__main__":
    geocoder = ImprovedGeocoder()
    
    print(f"\n{'='*60}")
    print(f"ТЕСТИРОВАНИЕ УЛУЧШЕННОГО ГЕОКОДЕРА")
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
