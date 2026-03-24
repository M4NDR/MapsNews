import feedparser
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import requests
from datetime import datetime
import re
from typing import Optional, List, Tuple
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

# Монтируем папку static для раздачи графики (в т.ч. скачанных картинок)
os.makedirs("static/images", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

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
            # Превращаем <br> в двойной перенос для надежного отделения абзацев
            for br in content_div.find_all("br"):
                br.replace_with("\n\n")
            
            # В конец каждого параграфа или блока тоже ставим двойной перенос
            for block in content_div.find_all(["p", "div", "h1", "h2", "h3", "li"]):
                block.append("\n\n")
                
            # Извлекаем текст, соединяя инлайн-теги (например <a>, <b>) просто пробелом
            text_content = content_div.get_text(separator=" ")
            
            # Бьём по реальным переносам
            raw_lines = text_content.split("\n")
            
            paragraphs = []
            skip_mode = False
            for line in raw_lines:
                # Очищаем от лишних (двойных, тройных) пробелов внутри и по краям
                clean_line = " ".join(line.split())
                
                # Защита от мусора
                lower_line = clean_line.lower()
                if lower_line.startswith("новости по теме") or lower_line.startswith("читайте также"):
                    skip_mode = True
                    continue
                
                if skip_mode:
                    # Если встречаем длинный полноценный абзац — это снова основная статья, выключаем пропуск
                    if len(clean_line) > 90:
                        skip_mode = False
                    else:
                        continue # Пропускаем мелкие "чужие" заголовки
                    
                if len(clean_line) > 5: # Игнорируем совсем короткий мусор
                    paragraphs.append(clean_line)
                    
            final_html = "".join([f"<p>{p}</p>\n" for p in paragraphs])
        
        else:
            # Fallback: просто ищем все <p>
            tags = soup.find_all('p')
            skip_mode = False
            for tag in tags:
                text = " ".join(tag.get_text(separator=" ").split())
                lower_text = text.lower()
                if lower_text.startswith("новости по теме") or lower_text.startswith("читайте также"):
                    skip_mode = True
                    continue
                
                if skip_mode:
                    if len(text) > 90:
                        skip_mode = False
                    else:
                        continue
                        
                if len(text) > 5: 
                    final_html += f"<p>{text}</p>\n"
            
            if not final_html:
                 # Super fallback
                text = soup.get_text(separator='\n')
                lines = []
                skip_mode = False
                for line in text.split('\n'):
                    clean_line = " ".join(line.split())
                    lower_line = clean_line.lower()
                    if lower_line.startswith("новости по теме") or lower_line.startswith("читайте также"):
                        skip_mode = True
                        continue
                        
                    if skip_mode:
                        if len(clean_line) > 100:
                            skip_mode = False
                        else:
                            continue
                            
                    if len(clean_line) > 40:
                        lines.append(clean_line)
                
                final_html = "".join([f"<p>{line}</p>\n" for line in lines])

        return final_html or "Текст не найден"

    except Exception as e:
        logger.error(f"[BS4] Ошибка загрузки контента: {e}")
        return ""

def download_image(url: str) -> Optional[str]:
    """ Скачивает картинку на диск и возвращает локальный URL (относительный) """
    if not url: return None
    if url.startswith("/static/"): 
        return url
        
    try:
        filename = url.split("/")[-1]
        if not filename or "?" in filename:
            import hashlib
            filename = hashlib.md5(url.encode()).hexdigest() + ".jpg"
            
        filepath = f"static/images/{filename}"
        
        # Скачиваем только если файла нет
        if not os.path.exists(filepath):
            r = requests.get(url, stream=True, timeout=10)
            if r.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
                        
        return f"/static/images/{filename}"
    except Exception as e:
        logger.error(f"[IMAGE] Ошибка скачивания {url}: {e}")
        return url

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

from json_geocoder import SimpleGeocoder

# Инициализация геокодера
simple_geocoder = SimpleGeocoder()

def extract_address_and_coords(text: str) -> Tuple[Optional[str], Optional[List[float]]]:
    return simple_geocoder.process_text(text, "")

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

                local_image = download_image(image)

                text_for_cat = (title + " " + preview).lower()
                category = "другое"
                for cat, words in CATEGORIES.items():
                    if any(w in text_for_cat for w in words):
                        category = cat
                        break

                if database.save_news({"url": url, "title": title, "preview": preview, "date": date, "image": local_image, "category": category}):
                    added += 1
            except Exception as e:
                logger.error(f"[RSS] Ошибка новости: {e}")
        logger.info(f"[RSS] Добавлено {added} новостей (всего: {database.get_news_count()})")
    except Exception as e:
        logger.error(f"[RSS] Критическая ошибка загрузки: {e}")

def background_geocoder():
    logger.info("[GEOCODER] Запущен (REGEX + YANDEX)")
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
                    address, coords = extract_address_and_coords(full_text)
                    
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

@app.get("/admin/logs")
def admin_logs(password: str = Query(...)):
    """Выводит логи парсинга новостей и геокодера"""
    if password != "123321":
        raise HTTPException(status_code=403, detail="Неверный пароль")
    return database.get_admin_logs(limit=200)