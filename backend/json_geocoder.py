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


class SimpleGeocoder:
    def __init__(self, cache_path: str = "geo_cache.json"):
        self.cache_path = cache_path
        self.cache = self._load_cache()
        logger.info("[REGEX GEOCODER] Инициализирован!")

    def _load_cache(self) -> dict:
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_cache(self):
        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[CACHE] Ошибка сохранения: {e}")

    def extract_address_from_text(self, text: str) -> Optional[str]:
        """
        Ищет адрес в тексте. Собирает все упоминания улиц и возвращает приоритетно тот адрес, 
        в котором указан номер дома. Если с номером дома нет, берет первый найденный.
        """
        # Маркеры оборачиваем в (?i: ...), чтобы только они игнорировали регистр, 
        # а названия улиц (с большой буквы) оставались строго чувствительны к регистру.
        markers = r"(?i:улиц[а-я]{1,3}|ул\.?|проспект[а-я]{0,2}|пр-?т?\.?|набережн[а-я]{2,3}|наб\.?|переул[а-я]{2}|пер\.?|площад[а-я]{1,2}|пл\.?|шоссе|ш\.?|алле[яие]|проезд[а-я]{0,2})"
        name = r"((?:[А-ЯЁ][а-яё]+|[0-9]{1,3}-?[а-яё]{0,2})(?:\s+[А-ЯЁ][а-яё]+){0,2})"
        
        # Захват "дома №33 по " или "д. 5 на "
        prefix_house = r"(?:(?i:д\.|дом[а-я]{0,2}|д)\s*(?:№)?\s*(\d+[а-яА-ЯёЁ]?(?:[/\-]\d+)?)\s+(?:по\s+|на\s+)?)?"
        
        # Захват номера дома после: "ул. Ленина, д. 5", "ул. Ленина №33", "ул. Вологодская, 1/2" 
        # Достаточным условием теперь является либо наличие маркера (д., дом), либо ЗАПЯТАЯ + цифра
        suffix_house = r"(?:\s*(?:[,]\s*(?:(?i:д\.|дом[а-я]{0,2}|д\.?|№))?\s*|(?i:д\.|дом[а-я]{0,2}|д\.?|№)\s*)(\d+[а-яА-ЯёЁ]?(?:[/\-]\d+)?))?"
        
        pattern1 = r"\b" + prefix_house + r"(?:" + markers + r")\s+" + name + suffix_house
        pattern2 = r"\b" + prefix_house + name + r"\s+(?:" + markers + r")\b" + suffix_house

        all_matches = []

        # Поиск по шаблону 1: ул. Ленина (БЕЗ re.IGNORECASE, чтобы [А-ЯЁ] работал корректно)
        for match in re.finditer(pattern1, text):
            found_str = match.group(0).strip()
            # Индексы групп в регулярке: 1 = префикс-дом, 2 = название улицы, 3 = суффикс-дом
            if "архангельск" in match.group(2).lower(): continue
            
            house_num = match.group(1) or match.group(3)
            all_matches.append((found_str, house_num))
            
        # Поиск по шаблону 2: Троицкий проспект
        for match in re.finditer(pattern2, text):
            found_str = match.group(0).strip()
            if "архангельск" in match.group(2).lower(): continue
            
            house_num = match.group(1) or match.group(3)
            all_matches.append((found_str, house_num))

        if not all_matches:
            return None

        # 1. Приоритет: ищем адрес, у которого захвачен логичный номер дома
        for found_str, house_num in all_matches:
            if house_num:
                # Фильтруем ложные срабатывания типа "ул. Ленина 2024" (год)
                if not re.match(r'^(19|20)\d{2}$', house_num):
                    return found_str
                    
        # 2. Если номеров домов нет, берем первый попавшийся адрес
        first_match = all_matches[0][0]
        # Если случайно захватился год в конце первого адреса, отрежем его для надежности
        year_match = re.search(r'\s+(19|20)\d{2}$', first_match)
        if year_match:
            first_match = first_match[:year_match.start()]
            
        return first_match

    def geocode_with_yandex(self, address: str) -> Optional[List[float]]:
        if not address: return None
        
        # Если в адресе явно не указан город, добавляем, чтобы геокодер искал внутри Архангельска
        if "архангельск" not in address.lower() and "северодвинск" not in address.lower():
            query_address = f"Архангельск, {address}"
        else:
            query_address = address

        # 1. Проверяем кэш
        if query_address in self.cache:
            logger.info(f"[CACHE] ✅ Найдено: {query_address}")
            return self.cache[query_address]
        
        try:
            url = (
                f"https://geocode-maps.yandex.ru/1.x/?apikey={GEOCODER_API_KEY}"
                f"&geocode={requests.utils.quote(query_address)}&format=json&results=1"
                f"&bbox={ARKH_OBLAST_BBOX}&rspn=1"
            )
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                members = data["response"]["GeoObjectCollection"]["featureMember"]
                
                if members:
                    pos = members[0]["GeoObject"]["Point"]["pos"]
                    lon, lat = map(float, pos.split())
                    coords = [lat, lon]
                    
                    self.cache[query_address] = coords
                    self._save_cache()
                    
                    return coords
            else:
                logger.error(f"[YANDEX] ❌ HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"[YANDEX] ❌ Ошибка: {e}")
        
        return None
    
    def process_text(self, title: str, content: str) -> Tuple[Optional[str], Optional[List[float]]]:
        """
        Обрабатывает текст новости и возвращает (адрес, координаты).
        """
        full_text = f"{title}. {content}"
        
        address = self.extract_address_from_text(full_text)
        if not address:
            return None, None
        
        coords = self.geocode_with_yandex(address)
        
        # Если Yandex API не нашел ничего, попробуем почистить адрес
        # (часто Yandex API плохо понимает слова с опечатками, или если адрес слишком сложный)
        # Мы оставляем первый найденный
        
        return address, coords
