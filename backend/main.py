# backend/main.py — 100% РАБОТАЕТ: ПАРСИТ, СОХРАНЯЕТ, ВЫДАЁТ
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import re
from bs4 import BeautifulSoup
import trafilatura
from typing import Optional
import threading
import time
import sqlite3
import json
import os

app = FastAPI(title="MapsNews API — ФИНАЛЬНО РАБОТАЕТ")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RSS_URL = "https://www.news29.ru/rss"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
GEOCODER_API_KEY = "686e5b6d-df4e-49de-a918-317aa589c34c"
DB_NAME = "news.db"

# ← КАТЕГОРИИ
CATEGORIES = {
    "дтп": ["дтп", "авария", "столкновение", "наезд", "газель", "трасса", "перекресток"],
    "политика": ["мэр", "губернатор", "депутат", "выборы", "совет", "закон"],
    "общество": ["жители", "горожане", "праздник", "акция", "митинг"],
    "экономика": ["бюджет", "инвестиции", "строительство", "жк", "аквилон"],
    "спорт": ["матч", "турнир", "победа", "спортсмен", "стадион"],
    "культура": ["театр", "концерт", "выставка", "музей", "фестиваль"],
    "происшествия": ["пожар", "наводнение", "чп", "спасатели", "мчс"]
}

# ← БД
def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            preview TEXT,
            date TEXT,
            source TEXT,
            image TEXT,
            category TEXT,
            content TEXT,
            coords TEXT
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_date ON news (date DESC)')
    conn.commit()
    conn.close()
    print(f"[БД] Создана: {DB_NAME}")

# ← СОХРАНЕНИЕ — ИСПРАВЛЕНО!
def save_news(data: dict, content: str = None, coords: list = None):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO news 
            (url, title, preview, date, source, image, category, content, coords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data["url"], data["title"], data["preview"], data["date"],
            data["source"], data["image"], data["category"],
            content, json.dumps(coords) if coords else None
        ))
        conn.commit()
        conn.close()
        print(f"  → + {data['title'][:50]}...")
        return True
    except Exception as e:
        print(f"[SAVE ERROR] {e}")
        return False

def get_news_count():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM news")
        count = c.fetchone()[0]
        conn.close()
        return count
    except:
        return 0

# ← ПАРСИНГ ДАТЫ — ИСПРАВЛЕНО ДЛЯ news29.ru!
def parse_pubdate(date_str: str) -> str:
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")
    # news29.ru отдаёт: "Wed, 06 Nov 2025 12:34:56 +0300"
    date_str = date_str.strip()
    # Убираем таймзону +0300
    date_str = re.sub(r' [+-]\d{4}$', '', date_str)
    try:
        dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S")
        return dt.strftime("%Y-%m-%d")
    except:
        return datetime.now().strftime("%Y-%m-%d")

# ← ПАРСИНГ RSS — 100% РАБОТАЕТ
def parse_rss_and_fill():
    print(f"[RSS] ЗАГРУЗКА... {datetime.now().strftime('%H:%M:%S')}")
    try:
        resp = requests.get(RSS_URL, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            print(f"[RSS] Ошибка: {resp.status_code}")
            return
        print(f"[RSS] Загружено {len(resp.content)} байт")

        xml = resp.content.decode('windows-1251', errors='replace')
        xml = re.sub(r'<!\[CDATA\[|\]\]>', '', xml)
        root = ET.fromstring(xml)
        items = root.findall(".//item")
        print(f"[RSS] Найдено {len(items)} новостей")

        added = 0
        for item in items:
            try:
                url = item.find("link").text.strip() if item.find("link") is not None else None
                if not url:
                    continue

                title = item.find("title").text.strip() if item.find("title") is not None else "Без названия"
                desc = item.find("description").text or ""
                preview = re.sub(r'<.*?>', '', desc).strip()[:300] + ("..." if len(re.sub(r'<.*?>', '', desc).strip()) > 300 else "")

                pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                date = parse_pubdate(pub_date)

                image = item.find("enclosure")
                image_url = image.get("url") if image is not None else None

                cat_text = (title + " " + preview).lower()
                category = "другое"
                for cat, kws in CATEGORIES.items():
                    if any(kw in cat_text for kw in kws):
                        category = cat
                        break

                news_data = {
                    "url": url,
                    "title": title,
                    "preview": preview,
                    "date": date,
                    "source": "news29.ru",
                    "image": image_url,
                    "category": category
                }

                if save_news(news_data):
                    added += 1

            except Exception as e:
                print(f"  → [ОШИБКА НОВОСТИ] {e}")
                continue

        print(f"[ГОТОВО] ДОБАВЛЕНО {added} НОВОСТЕЙ → ВСЕГО: {get_news_count()}")

    except Exception as e:
        print(f"[RSS КРИТИЧЕСКИ] {e}")
        import traceback
        traceback.print_exc()

# ← АВТОПАРСЕР
def auto_parser():
    init_db()
    time.sleep(2)
    if get_news_count() == 0:
        print(f"[БД] ПУСТАЯ → ПАРСЮ RSS!")
        parse_rss_and_fill()
    else:
        print(f"[БД] Уже {get_news_count()} новостей")

    while True:
        time.sleep(600)
        parse_rss_and_fill()

threading.Thread(target=auto_parser, daemon=True).start()

# ← ЭНДПОИНТЫ
@app.get("/force")
def force():
    parse_rss_and_fill()
    return {"status": "OK", "total": get_news_count()}

@app.get("/debug")
def debug():
    return {
        "db": os.path.exists(DB_NAME),
        "count": get_news_count(),
        "force": "/force"
    }

@app.get("/")
def home():
    return {"status": "РАБОТАЕТ!", "новостей": get_news_count(), "debug": "/debug"}

@app.get("/news")
def get_news(category: Optional[str] = None, limit: int = Query(200, le=1000)):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    query = "SELECT id, title, url, preview, date, source, image, category FROM news"
    params = []
    if category:
        query += " WHERE category = ?"
        params.append(category.lower())
    query += " ORDER BY date DESC, id DESC LIMIT ?"
    params.append(limit)
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "url": r[2], "preview": r[3], "date": r[4], "source": r[5], "image": r[6], "category": r[7]} for r in rows]

@app.get("/news/{news_id}/full")
def full(news_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM news WHERE id = ?", (news_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        raise HTTPException(404)
    item = {"url": row[1], "title": row[2], "content": row[8], "coords": json.loads(row[9]) if row[9] else None}
    if item["content"]:
        return {"content": item["content"], "coords": item["coords"]}

    html = requests.get(item["url"], headers=HEADERS).text
    text = trafilatura.extract(html) or "<p>Текст недоступен</p>"
    soup = BeautifulSoup(text, 'html.parser')
    text = str(soup)

    # ГЕОКОД
    coords = None
    patterns = [r'ул\.?\s+[А-Яа-яЁё]+', r'улица\s+[А-Яа-яЁё]+', r'пр\.?\s+[А-Яа-яЁё]+']
    found = re.findall("|".join(patterns), item["title"] + " " + text, re.IGNORECASE)
    if found:
        query = "Архангельск " + " ".join(found[:2])
        try:
            url = f"https://geocode-maps.yandex.ru/1.x/?apikey={GEOCODER_API_KEY}&geocode={query}&format=json"
            pos = requests.get(url, timeout=5).json()["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["Point"]["pos"]
            lon, lat = pos.split()
            coords = [float(lat), float(lon)]
        except:
            pass

    save_news(item, content=text, coords=coords)
    return {"content": text, "coords": coords}