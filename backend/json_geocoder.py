import os
import json
import requests
import re
import logging
from typing import Optional, List, Tuple

# Отключаем прокси для всех запросов
_session = requests.Session()
_session.verify = False
_session.trust_env = False

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

    def _clean_address_for_yandex(self, address: str) -> str:
        """
        Очищает адрес от лишних слов перед отправкой в Яндекс.Геокодер.
        """
        # Сначала преобразуем "у дома №9 по проспекту Бутомы" → "проспект Бутомы 9"
        # Поддерживаем варианты: "у дома №9 по...", "дома №9 по...", "у дома 9 по..."
        match = re.match(r'^(?i:у\s+)?дома\s*(?:№)?\s*(\d+[а-яА-ЯёЁ]?)\s+по\s+(.+)$', address)
        if match:
            house_num = match.group(1)
            street = match.group(2)
            address = f"{street} {house_num}"
        
        # Убираем "у дома №..." из любой позиции (если не было "по")
        address = re.sub(r'\s*(?i:у\s+дома\s*(?:№)?\s*)\s*', ' ', address)

        # Убираем предлоги в начале (На, В, По)
        address = re.sub(r'(?i:^(на|в|по)\s+)', '', address)

        # Если адрес начинается с слова с большой буквы, за которым следует "на/в" + название с большой буквы,
        # то первое слово скорее всего лишнее (например "Авария на Ленинградском...")
        match = re.match(r'^([А-ЯЁ][а-яё]+)\s+(?i:на|в|по)\s+([А-ЯЁ])', address)
        if match:
            # Удаляем первое слово и предлог
            address = re.sub(r'^[А-ЯЁ][а-яё]+\s+(?i:на|в|по)\s+', '', address)

        # Убираем лишние пробелы
        return ' '.join(address.split())

    def extract_address_from_text(self, text: str) -> Optional[str]:
        """
        Ищет адрес в тексте. Собирает все упоминания улиц и возвращает приоритетно тот адрес,
        в котором указан номер дома. Если с номером дома нет, берет первый найденный.
        """
        # Маркеры с обязательным пробелом после сокращений (чтобы "пр" не захватывалось в "проблема")
        # \s? после сокращений означает опциональный пробел (для конца текста/предложения)
        # Расширенные окончания для разных падежей (у, е, ом, у и т.д.)
        markers = r"(?i:улиц[а-я]{1,4}\s?|ул\.\s?|проспект[а-я]{0,3}\s?|пр-?т?\.\s?|набережн[а-я]{2,4}\s?|наб\.\s?|переул[а-я]{2,3}\s?|пер\.\s?|площад[ьи]\s?|пл\.\s?|шоссе\s?|ш\.\s?|алле[яие]\s?|проезд[а-я]{0,3}\s?|дворец\s+спорта\s?|дворц[а-я]{1,2}\s+спорта\s?|стадион[а-я]{0,3}\s?|парк[а-я]{0,2}\s?|сквер[а-я]{0,2}\s?|театр[а-я]{0,2}\s?|музе[йяю]\s?|тц\s?|трц\s?)"
        # Название улицы: 1-3 слова (первое с большой буквы, остальные могут быть с маленькой - для "Обуховской обороны")
        name = r"((?:[А-ЯЁ][а-яё]+(?:-[а-яё]+)?|[0-9]{1,3}-?[а-яё]{0,2})(?:\s+[а-яА-Яё]+(?:-[а-яё]+)?){0,2})"

        # Захват "дома №33 по " или "д. 5 на " или "у дома №441"
        prefix_house = r"(?:(?i:д\.|дом[а-я]{0,2}|д|у\s+дома)\s*(?:№)?\s*(\d+[а-яА-ЯёЁ]?(?:[/\-]\d+)?)\s+(?:по\s+|на\s+)?)?"

        # Захват номера дома после: "ул. Ленина, д. 5", "ул. Ленина №33", "ул. Вологодская, 1/2"
        # Также захватываем просто цифру после названия улицы (например "Ленинградский проспект 441")
        # И конструкцию "у дома №441" в конце
        # \s* в начале потому что маркер уже включает пробел после себя
        suffix_house = r"(?:\s*(?:[,]\s*(?:(?i:д\.|дом[а-я]{0,2}|д\.?|№))?\s*|(?i:д\.|дом[а-я]{0,2}|д\.?|№|у\s+дома)\s*)(\d+[а-яА-ЯёЁ]?(?:[/\-]\d+)?))?"

        pattern1 = r"\b" + prefix_house + r"(?:" + markers + r")\s+" + name + suffix_house
        pattern2 = r"\b" + prefix_house + name + r"\s+(?:" + markers + r")\b" + suffix_house
        # Паттерн 3: для случаев типа "Ленинградский проспект 441" (название + маркер + номер)
        # Требует номер дома после маркера, чтобы избежать ложных срабатываний типа "Автобус пр..."
        pattern3 = r"\b" + name + r"\s+(?:" + markers + r")(\d+[а-яА-ЯёЁ]?(?:[/\-]\d+)?)"
        # Паттерн 3c: для случаев типа "на улице Ленина 5" (предлог + маркер + название + номер)
        pattern3c = r"(?i:на|у)\s+(?:" + markers + r")" + name + r"\s+(\d+[а-яА-ЯёЁ]?(?:[/\-]\d+)?)"
        # Паттерн 3b: для случаев типа "улица Ленина", "проспект Обуховской обороны" (маркер + название БЕЗ номера)
        # Здесь название должно быть минимум 2 слова или второе слово с большой буквы
        pattern3b = r"\b(?:" + markers + r")([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)(?:\s|$)"
        # Паттерн 3d: для случаев типа "ул. Ленина 5", "проспект Обуховской обороны 12" (маркер + название + номер)
        pattern3d = r"\b(?:" + markers + r")([А-ЯЁ][а-яё]+(?:\s+[а-яА-Яё]+)?)\s+(\d+[а-яА-ЯёЁ]?(?:[/\-]\d+)?)"
        # Паттерн 4: для случаев типа "у дома 441 на Ленинградском проспекте"
        pattern4 = r"(?i:у\s+дома)\s*(?:№)?\s*(\d+[а-яА-ЯёЁ]?(?:[/\-]\d+)?)\s+(?:на\s+)?" + r"(?:" + markers + r")\s+" + name
        # Паттерн 5: для случаев типа "На Ленинградском проспекте у дома 441" (маркер + название + у дома)
        pattern5 = r"(?:" + markers + r")\s+" + name + r"\s+(?i:у\s+дома)\s*(?:№)?\s*(\d+[а-яА-ЯёЁ]?(?:[/\-]\d+)?)?"
        # Паттерн 6: для случаев типа "на/На Ленинградском проспекте у дома 441" (предлог + название + маркер + у дома)
        # \b в начале чтобы не захватывать "Авария на..."
        pattern6 = r"\b(?i:на\s+)" + name + r"\s+(?:" + markers + r")\s+(?i:у\s+дома)\s*(?:№)?\s*(\d+[а-яА-ЯёЁ]?(?:[/\-]\d+)?)?"

        all_matches = []

        # Поиск по шаблону 1: ул. Ленина
        for match in re.finditer(pattern1, text):
            found_str = match.group(0).strip()
            if "архангельск" in match.group(2).lower(): continue
            house_num = match.group(1) or match.group(3)
            all_matches.append((found_str, house_num))

        # Поиск по шаблону 2: Троицкий проспект
        for match in re.finditer(pattern2, text):
            found_str = match.group(0).strip()
            if "архангельск" in match.group(2).lower(): continue
            house_num = match.group(1) or match.group(3)
            all_matches.append((found_str, house_num))

        # Поиск по шаблону 3: Ленинградский проспект 441 (название + маркер + номер)
        for match in re.finditer(pattern3, text):
            found_str = match.group(0).strip()
            if "архангельск" in match.group(1).lower(): continue
            house_num = match.group(2)
            all_matches.append((found_str, house_num))

        # Поиск по шаблону 3c: на улице Ленина 5 (предлог + маркер + название + номер)
        for match in re.finditer(pattern3c, text):
            found_str = match.group(0).strip()
            if "архангельск" in match.group(1).lower(): continue  # Группа 1 - название улицы
            house_num = match.group(2)  # Группа 2 - номер дома
            all_matches.append((found_str, house_num))

        # Поиск по шаблону 3b: улица Ленина, проспект Обуховской обороны (маркер + название БЕЗ номера)
        for match in re.finditer(pattern3b, text):
            found_str = match.group(0).strip()
            if "архангельск" in match.group(1).lower(): continue
            # Нет номера дома, добавляем без приоритета
            all_matches.append((found_str, None))

        # Поиск по шаблону 3d: ул. Ленина 5, проспект Обуховской обороны 12 (маркер + название + номер)
        for match in re.finditer(pattern3d, text):
            found_str = match.group(0).strip()
            if "архангельск" in match.group(1).lower(): continue
            house_num = match.group(2)
            all_matches.append((found_str, house_num))

        # Поиск по шаблону 4: у дома 441 на Ленинградском проспекте
        for match in re.finditer(pattern4, text):
            found_str = match.group(0).strip()
            if "архангельск" in match.group(3).lower(): continue
            house_num = match.group(1)
            all_matches.append((found_str, house_num))

        # Поиск по шаблону 5: На Ленинградском проспекте у дома 441
        for match in re.finditer(pattern5, text):
            found_str = match.group(0).strip()
            if "архангельск" in match.group(2).lower(): continue
            house_num = match.group(3)
            all_matches.append((found_str, house_num))

        # Поиск по шаблону 6: на/На Ленинградском проспекте у дома 441
        for match in re.finditer(pattern6, text):
            found_str = match.group(0).strip()
            if "архангельск" in match.group(1).lower(): continue
            house_num = match.group(2)
            all_matches.append((found_str, house_num))

        if not all_matches:
            return None

        # 1. Приоритет: ищем адрес, у которого захвачен логичный номер дома
        for found_str, house_num in all_matches:
            if house_num:
                # Фильтруем ложные срабатывания типа "ул. Ленина 2024" (год)
                if not re.match(r'^(19|20)\d{2}$', house_num):
                    return found_str

        # 2. Если номеров домов нет, ищем адрес с маркером + название (паттерн 3b)
        for found_str, house_num in all_matches:
            # Проверяем, что это не ложное срабатывание (маркер + короткое слово)
            if not house_num and found_str:
                # Проверяем, содержит ли адрес маркер улицы (с пробелом после!)
                markers_pattern = r"(?i:улиц[а-я]{1,3}\s|ул\.\s|проспект[а-я]{0,2}\s|пр-?т?\.\s|набережн[а-я]{2,3}\s|наб\.\s|переул[а-я]{2}\s|пер\.\s|площад[ьи]\s|пл\.\s|шоссе\s|ш\.\s)"
                if re.search(markers_pattern, found_str):
                    # Проверяем, что название не слишком короткое (минимум 4 символа)
                    words = found_str.split()
                    for word in words:
                        if len(word) > 3 and word[0].isupper():
                            return found_str

        # 3. Если ничего не найдено, берем первый попавшийся адрес
        first_match = all_matches[0][0]
        # Если случайно захватился год в конце первого адреса, отрежем его для надежности
        year_match = re.search(r'\s+(19|20)\d{2}$', first_match)
        if year_match:
            first_match = first_match[:year_match.start()]

        return first_match

    def geocode_with_yandex(self, address: str) -> Optional[List[float]]:
        if not address: return None

        # Очищаем адрес от лишних слов перед отправкой в Яндекс
        clean_address = self._clean_address_for_yandex(address)
        logger.info(f"[GEO] Исходный: '{address}' → Очищенный: '{clean_address}'")

        # Если в адресе явно не указан город, добавляем, чтобы геокодер искал внутри Архангельска
        if "архангельск" not in clean_address.lower() and "северодвинск" not in clean_address.lower():
            query_address = f"Архангельск, {clean_address}"
        else:
            query_address = clean_address

        # 1. Проверяем кэш
        if query_address in self.cache:
            logger.info(f"[CACHE] ✅ Найдено: {query_address}")
            return self.cache[query_address]

        # 2. Запрашиваем у Yandex API
        url = (
            f"https://geocode-maps.yandex.ru/1.x/?apikey={GEOCODER_API_KEY}"
            f"&geocode={requests.utils.quote(query_address)}&format=json&results=1"
            f"&bbox={ARKH_OBLAST_BBOX}&rspn=1"
        )

        import time
        for attempt in range(3):
            try:
                response = _session.get(url, timeout=15)

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
                        # Яндекс ничего не нашел - нет смысла продолжать цикл
                        return None
                else:
                    logger.error(f"[YANDEX] ❌ HTTP {response.status_code}")
                    break
            except Exception as e:
                logger.warning(f"[YANDEX] Попытка {attempt+1}/3 ❌ Ошибка соединения (возможно SSL разрыв): {e}")
                if attempt < 2:
                    time.sleep(2)

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
