import feedparser
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
from datetime import datetime
import re
from typing import Optional, List
import threading
import time
import os
import logging

import database

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MapsNews API — news29.ru (Fixed)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# === КОНФИГУРАЦИЯ ===
RSS_URL = "https://www.news29.ru/rss"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
GEOCODER_API_KEY = os.getenv("GEOCODER_API_KEY", "686e5b6d-df4e-49de-a918-317aa589c34c")
ARKH_OBLAST_BBOX = "35.5,62.8~49.0,67.5"
UPDATE_INTERVAL = 900 # 15 минут

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def clean_text(text: str) -> str:
    """Очищает текст от лишних пробелов."""
    return re.sub(r'\s+', ' ', text or "").strip()

def parse_pubdate(date_str: str) -> str:
    """Парсит дату из RSS."""
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")
    date_str = re.sub(r' [+-]\d{4}$', '', date_str.strip())
    try:
        dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S")
        return dt.strftime("%Y-%m-%d")
    except:
        return datetime.now().strftime("%Y-%m-%d")

def extract_content_with_bs4(url: str) -> str:
    """
    Загружает страницу и извлекает контент с сохранением форматирования (абзацев).
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding 
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Убираем скрипты и стили
        for script in soup(["script", "style"]):
            script.decompose()

        content_div = soup.find('div', class_='news-text') or soup.find('div', class_='fulltext') or soup.find('article')
        
        final_html = ""
        
        if content_div:
            # Если нашли контейнер, пробуем извлечь текст с учетом <br>
            # Заменяем двойные <br> на параграфы
            for br in content_div.find_all("br"):
                br.replace_with("\n")
            
            text_content = content_div.get_text(separator="\n", strip=True)
            paragraphs = [p.strip() for p in text_content.split("\n") if len(p.strip()) > 20]
            
            final_html = "".join([f"<p>{p}</p>\n" for p in paragraphs])
        
        else:
            # Fallback: ищем все P
            tags = soup.find_all('p')
            for tag in tags:
                text = tag.get_text(strip=True)
                if len(text) > 20: 
                    final_html += f"<p>{text}</p>\n"
            
            if not final_html:
                 # Super fallback
                text = soup.get_text(separator='\n', strip=True)
                lines = [line for line in text.split('\n') if len(line) > 50]
                final_html = "".join([f"<p>{line}</p>\n" for line in lines])

        return final_html or "Текст не найден"

    except Exception as e:
        logger.error(f"[BS4] Ошибка загрузки контента: {e}")
        return ""

# === СЛОВАРИ И ДАННЫЕ ===
CATEGORIES = {
    "дтп": ["дтп", "авария", "столкновение", "сбил", "наезд", "опрокинулся", "лобовое", "гибдд", "гаи", "перекресток"],
    "происшествия": ["пожар", "возгорание", "мчс", "чп", "утонул", "пропал", "наводнение", "взрыв", "обрушение", "скорая", "смерть"],
    "криминал": ["полиция", "задержан", "вор", "кража", "грабеж", "наркотики", "суд", "приговор", "уголовное дело"],
    "политика": ["мэр", "губернатор", "депутат", "дума", "выборы", "администрация"],
    "жкх": ["отопление", "тепло", "вода", "лифт", "мусор", "тариф", "жкх", "прорыв трубы"],
    "экономика": ["бюджет", "инвестиции", "стройка", "аквилон", "порт", "экономия", "лдк"],
    "общество": ["жители", "праздник", "акция", "ветеран", "школа", "больница", "поликлиника"],
    "спорт": ["водник", "матч", "хоккей", "стадион труд", "турнир", "победа"],
    "культура": ["театр", "концерт", "фестиваль", "музей", "выставка", "чумабаровка"],
    "образование": ["сафу", "сгму", "университет", "студент", "школа", "лицей", "егэ"]
}

KNOWN_PLACES = {
    "архангельский суд": "Архангельск, ул. Гайдара, 8",
    "областной суд": "Архангельск, ул. Гайдара, 8",
    "северодвинский суд": "Северодвинск, ул. Ломоносова, 73",
    "ломоносовский суд": "Архангельск, пр. Ломоносова, 202",
    "октябрьский суд": "Архангельск, ул. Гагарина, 11",
    "исакогорский суд": "Архангельск, ул. Дрейера, 99",
    "соломбальский суд": "Архангельск, пр. Никольский, 15",
    "драмтеатр": "Архангельск, площадь Ленина, 1",
    "драмтеатра": "Архангельск, площадь Ленина, 1",
    "стадион труд": "Архангельск, ул. Розинга, 19",
    "кинотеатр мир": "Архангельск, пр. Троицкий, 55",
    "дк строитель": "Северодвинск, ул. Советская, 10",
    "дворец молодежи строитель": "Северодвинск, ул. Советская, 10",
    "поликлиника №3": "Архангельск, ул. Победы, 67",
    "поликлиника 3": "Архангельск, ул. Победы, 67",
    "поликлиника №2": "Архангельск, пр. Ленинградский, 261",
    "поликлиника 2": "Архангельск, пр. Ленинградский, 261",
    "поликлиника №1": "Архангельск, пр. Ломоносова, 292",
}

WHITELIST_ARCHANGELSK = {
    'тц "макси"', 'макси', 'тц макси', 'макси молл',
    'тц "рико"', 'рико', 'тц рико',
    'тц "европа"', 'европа сити молл', 'европа', 'тц европа',
    'тц "сигма"', 'сигма',
    'тц "титан арена"', 'титан арена', 'титан',
    'тц "дельта"', 'дельта',
    'тц "солнечный"', 'солнечный',
    'трк "гранд плаза"', 'гранд плаза',
    'тц "на троицком"', 'на троицком',
    'тц "морской"', 'морской',
    'тц "премьер"', 'премьер',
    'первая городская больница', '1 гб', 'гб №1', 'городская больница №1',
    'семашко', 'больница семашко',
    'аокб', 'архангельская областная клиническая больница',
    'областная больница', 'аоκб',
    'детская областная больница', 'докб', 'детская окб',
    'поликлиника №1', 'поликлиника №2', 'поликлиника №3', 'поликлиника №4',
    'поликлиника №6', 'поликлиника №7', 'поликлиника №14',
    'городская поликлиника №1', 'гп №1', 'гп №2',
    'детская поликлиника №1', 'детская поликлиника №2', 'детская поликлиника №3',
    'поликлиника литвинова', 'стоматологическая поликлиника',
    'аптека "горизонт"', 'горизонт',
    'аптека "максифарм"', 'максифарм',
    'аптека "ригла"', 'ригла',
    'аптека "столички"', 'столички',
    'аптека "здравсити"',
    'детский сад №', 'д/с №', 'дс №',
    'школа №', 'гимназия №', 'лицей №',
    'сафу', 'северный медицинский университет',
    'поморский университет', 'с(а)фу',
    'лвт', 'ломоносовский дворец творчества',
    'дк', 'дом культуры',
    'драмтеатр', 'театр драмы', 'театр кукол',
    'кинотеатр "мираж"', 'мираж синема', 'мираж',
    'морской-речной вокзал', 'морвокзал',
    'северный рынок', 'центральный рынок', 'привокзальный рынок'
}

WHITELIST_LOWER = {item.lower().strip('"') for item in WHITELIST_ARCHANGELSK}

# === ГЕОКОДЕР ===
from natasha import (
    Segmenter, MorphVocab, AddrExtractor, NewsEmbedding, NewsNERTagger, Doc
)

segmenter = Segmenter()
morph_vocab = MorphVocab()
emb = NewsEmbedding()
ner_tagger = NewsNERTagger(emb)
addr_extractor = AddrExtractor(morph_vocab)

def extract_address(text: str) -> Optional[str]:
    text_lower = text.lower()
    for key, addr in KNOWN_PLACES.items():
        if key in text_lower:
            return addr
    for item in WHITELIST_LOWER:
        if item in text_lower:
            if "архангельск" not in item and "северодвинск" not in item:
                 return f"Архангельск, {item}"
            return item
    try:
        doc = Doc(text)
        doc.segment(segmenter)
        doc.tag_ner(ner_tagger)
        for span in doc.spans:
            val = span.text.strip('«»"\'')
            val_lower = val.lower()
            ignore_list = [
                "архангельск", "архангельская область", "область", "россия", "северодвинск", "поморье",
                "регион", "ненецкий автономный округ", "нао", "рф",
                "news29", "news29.ru", "сбер", "сбербанк", "мегафон", "мтс", "билайн", "теле2",
                "vk", "вконтакте", "telegram", "facebook", "instagram", "youtube", "megapteka.ru"
            ]
            if any(ign in val_lower for ign in ignore_list): continue
            if span.type == 'ORG' or span.type == 'LOC':
                 if len(val) > 3: return val
        matches = list(addr_extractor(text))
        for match in matches:
            fact = match.fact
            parts = []
            if hasattr(fact, 'street') and fact.street: parts.append(fact.street)
            if hasattr(fact, 'building') and fact.building: parts.append(fact.building)
            if parts: return ", ".join(parts)
    except Exception as e:
        logger.error(f"[NATASHA NER] Ошибка: {e}")
    return "Архангельск"

def get_coords_from_yandex(query: str) -> Optional[List[float]]:
    if not query: return None
    try:
        url = (
            f"https://geocode-maps.yandex.ru/1.x/?apikey={GEOCODER_API_KEY}"
            f"&geocode={requests.utils.quote(query)}&format=json&results=1"
            f"&bbox={ARKH_OBLAST_BBOX}&rspn=1"
        )
        logger.info(f"[GEOCODER] → {query}")
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            members = data["response"]["GeoObjectCollection"]["featureMember"]
            if members:
                lon, lat = map(float, members[0]["GeoObject"]["Point"]["pos"].split())
                logger.info(f"[GEOCODER] УСПЕХ → [{lat:.6f}, {lon:.6f}]")
                return [lat, lon]
        logger.info(f"[GEOCODER] Не найдено")
    except Exception as e:
        logger.error(f"[GEOCODER] Ошибка: {e}")
    return None

def parse_rss_and_fill():
    logger.info("[RSS] Загрузка новостей через FEEDPARSER...")
    try:
        feed = feedparser.parse(RSS_URL)
        if feed.bozo:
            logger.warning(f"[RSS] Ошибка парсинга XML: {feed.bozo_exception}")
        added = 0
        for entry in feed.entries:
            try:
                url = clean_text(entry.get("link", ""))
                if not url: continue
                title = clean_text(entry.get("title", "Без заголовка"))
                
                raw_desc = entry.get("description", "") or entry.get("summary", "")
                desc_soup = BeautifulSoup(raw_desc, 'html.parser')
                desc_clean = desc_soup.get_text(strip=True)
                preview = desc_clean[:300] + ("..." if len(desc_clean) > 300 else "")
                
                date_str = entry.get("published", "")
                date = parse_pubdate(date_str)
                
                image = None
                for enc in entry.get("enclosures", []):
                    if enc.get("type", "").startswith("image/"):
                        image = enc.get("href")
                        break
                if not image and "media_content" in entry:
                    image = entry.media_content[0].get("url")

                text_for_cat = (title + " " + preview).lower()
                category = "другое"
                for cat, words in CATEGORIES.items():
                    if any(w in text_for_cat for w in words):
                        category = cat
                        break

                if database.save_news({"url": url, "title": title, "preview": preview, "date": date, "image": image, "category": category}):
                    added += 1
            except Exception as e:
                logger.error(f"[RSS] Ошибка новости: {e}")
        logger.info(f"[RSS] Добавлено {added} новостей (всего: {database.get_news_count()})")
    except Exception as e:
        logger.error(f"[RSS] Критическая ошибка: {e}")

def background_geocoder():
    logger.info("[GEOCODER] Запущен (NATASHA + YANDEX + BS4 Content)")
    while True:
        try:
            items = database.get_uncoded_news(limit=6)
            if not items:
                time.sleep(60)
                continue
            for item in items:
                try:
                    content = item.get("content")
                    if not content or content == "Ошибка загрузки":
                        content = extract_content_with_bs4(item["url"])
                    
                    clean_content_for_geo = BeautifulSoup(content, "html.parser").get_text(separator=" ", strip=True)
                    full_text = f"{item['title']} {clean_content_for_geo}"
                    address = extract_address(full_text)
                    
                    coords = None
                    if address:
                        coords = get_coords_from_yandex(address)
                    
                    database.update_news_content_and_coords(item["id"], content, coords, address=address)
                    
                    log_addr = address or '—'
                    log_coords = coords or 'None'
                    logger.info(f"[GEO] {item['id']} → {log_addr} → {log_coords}")
                    time.sleep(1.5)
                except Exception as e:
                    logger.error(f"[GEOCODER] Ошибка {item.get('id', '?')}: {e}")
            time.sleep(10)
        except Exception as e:
            logger.error(f"[GEOCODER LOOP] {e}")
            time.sleep(60)

def auto_parser():
    database.init_db()
    # Первая загрузка через 2 секунды после старта, чтобы не блочить
    time.sleep(2)
    parse_rss_and_fill()
    while True:
        time.sleep(UPDATE_INTERVAL)
        parse_rss_and_fill()

@app.on_event("startup")
async def startup():
    threading.Thread(target=auto_parser, daemon=True).start()
    threading.Thread(target=background_geocoder, daemon=True).start()

@app.get("/force")
def force():
    parse_rss_and_fill()
    return {"status": "OK", "новостей": database.get_news_count()}

@app.get("/")
def root():
    return {"status": "работает", "новостей": database.get_news_count()}

@app.get("/news")
def news(category: Optional[str] = None, limit: int = Query(200, le=1000)):
    return database.get_all_news(limit, category)

@app.get("/news/{news_id}/full")
def full(news_id: int):
    item = database.get_news_by_id(news_id)
    if not item:
        raise HTTPException(404)
    if not item["content"]:
        content = extract_content_with_bs4(item["url"])
        database.update_news_content_and_coords(item["id"], content, item["coords"])
        item["content"] = content
    return item