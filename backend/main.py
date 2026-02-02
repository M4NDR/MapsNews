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

# Словари удалены - функционал перенесен в json_geocoder.py и streets_database.json

# === ГЕОКОДЕР ===
from json_geocoder import SimpleGeocoder
from natasha import (
    Segmenter, MorphVocab, AddrExtractor, NewsEmbedding, NewsNERTagger, Doc
)

# Инициализация
simple_geocoder = SimpleGeocoder()
segmenter = Segmenter()
morph_vocab = MorphVocab()
addr_extractor = AddrExtractor(morph_vocab)
emb = NewsEmbedding()
ner_tagger = NewsNERTagger(emb)

def extract_address(text: str) -> Optional[str]:
    """
    Извлекает адрес. 
    1. Сначала ищет точное совпадение улицы по JSON-базе.
    2. Если не найдено — использует Natasha NLP (медленнее, но гибче).
    """
    # 1. Быстрый поиск через JSON
    street = simple_geocoder.find_street_in_text(text)
    if street:
        building = simple_geocoder.extract_building_number(text, street)
        if building:
            return f"Архангельск, {street}, {building}"
        return f"Архангельск, {street}"

    # 2. Fallback: Natasha NLP
    try:
        doc = Doc(text)
        doc.segment(segmenter)
        doc.tag_ner(ner_tagger)
        
        matches = list(addr_extractor(text))
        for match in matches:
            fact = match.fact
            parts = []
            if hasattr(fact, 'street') and fact.street: parts.append(fact.street)
            if hasattr(fact, 'building') and fact.building: parts.append(fact.building)
            
            if parts: 
                addr = ", ".join(parts)
                if "архангельск" not in addr.lower() and "северодвинск" not in addr.lower():
                    return f"Архангельск, {addr}"
                return addr

        for span in doc.spans:
            val = span.text.strip('«»"\'')
            val_lower = val.lower()
            if len(val) < 4: continue
            if span.type == 'ORG' or span.type == 'LOC':
                 # Простая фильтрация стоп-слов внутри Natasha-блока уже избыточна, 
                 # если JSON перехватывает основные улицы, но оставим для надежности
                 return val
                 
    except Exception as e:
        logger.error(f"[GEO] Ошибка NLP: {e}")
    
    return None

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
    logger.info("[RSS] Загрузка новостей через REQUESTS + FEEDPARSER...")
    try:
        # Скачиваем с заголовками, чтобы пройти защиту от ботов
        response = requests.get(RSS_URL, headers=HEADERS, timeout=20)
        response.raise_for_status()
        
        feed = feedparser.parse(response.content)
        
        if feed.bozo:
            logger.warning(f"[RSS] Warning парсинга XML: {feed.bozo_exception}")

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
        logger.error(f"[RSS] Критическая ошибка загрузки: {e}")

def background_geocoder():
    logger.info("[GEOCODER] Запущен (JSON + NATASHA + YANDEX)")
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
                    
                    # Если адрес не найден, пишем метку, чтобы не брать снова
                    final_address = address if address else "NOT_FOUND"
                    
                    database.update_news_content_and_coords(item["id"], content, coords, address=final_address)
                    
                    log_addr = address or 'НЕТ АДРЕСА'
                    log_coords = coords or '—'
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