import feedparser
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from datetime import datetime
import re
from typing import Optional, List, Tuple
import threading
import time
import os
import logging
import urllib3

# Отключаем предупреждения о небезопасных SSL-соединениях
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
RSS_URLS = [
    "https://www.news29.ru/rss",
    "http://www.news29.ru/rss",
    "https://news29.ru/rss",
    "http://news29.ru/rss",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
GEOCODER_API_KEY = os.getenv("GEOCODER_API_KEY", "686e5b6d-df4e-49de-a918-317aa589c34c")
ARKH_OBLAST_BBOX = "35.5,62.8~49.0,67.5"
UPDATE_INTERVAL = 900 # 15 минут

# Создаём сессию с обходом SSL-ошибок
def create_ssl_session():
    """Создаёт requests.Session с обходом проблем SSL и прокси"""
    session = requests.Session()
    session.verify = False  # Отключаем верификацию SSL
    session.trust_env = False  # Игнорируем прокси из окружения (WinError 10061)
    return session

# Глобальная сессия для RSS
rss_session = create_ssl_session()

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
        # Используем rss_session с отключенным прокси
        resp = rss_session.get(url, headers=HEADERS, timeout=15)
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
            # Используем глобальную сессию с отключенным прокси
            r = rss_session.get(url, stream=True, timeout=10)
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
    "дтп": ["дтп", "авари", "столкнов", "сбил", "наезд", "опрокинул", "лобовое", "гибдд", "дорожно-транспорт", "въехал в"],
    "происшествия": ["пожар", "возгоран", "мчс", "чп", "утонул", "пропал", "наводнен", "взрыв", "обрушен", "скорая", "погиб", "смерт", "спасател", "труп", "эвакуаци"],
    "криминал": ["полици", "задержан", "краж", "грабеж", "ограбл", "наркоти", "суд", "приговор", "уголовн", "мошенни", "убийств", "коррупц", "прокуратур", "мвд", "фсб"],
    "политика": ["мэр ", "губернатор", "депутат", "дума", "выборы", "администраци", "законопроект", "власт", "чиновник", "цыбульск", "морев"],
    "жкх": ["отоплен", "теплоснабж", "водоканал", "тариф", "жкх", "прорыв труб", "тгк-2", "рвк-", "электроснабж", "управляющая компани", "коммунальн", "снег", "уборка"],
    "экономика": ["бюджет", "инвестици", "строительств", "аквилон", "порт", "экономи", "лдк", "завод", "предприяти", "бизнес", "налог", "финанс"],
    "общество": ["жител", "праздник", "акци", "ветеран", "пенсионер", "волонтер", "помор", "благоустройств", "парк", "сквер", "общественн"],
    "спорт": ["водник", "матч", "хоккей", "стадион", "турнир", "соревновани", "чемпионат", "медал", "тренер", "фитнес", "спорт"],
    "культура": ["театр", "концерт", "фестивал", "музей", "выставк", "чумабаровк", "искусств", "художник", "писател", "музыкант", "премьер"],
    "образование": ["сафу", "сгму", "университет", "студент", "школ", "лицей", "егэ", "учител", "педагог", "образовани", "колледж", "детский сад"]
}

from json_geocoder import SimpleGeocoder

# Инициализация геокодера
simple_geocoder = SimpleGeocoder()

def extract_address_and_coords(text: str) -> Tuple[Optional[str], Optional[List[float]]]:
    return simple_geocoder.process_text(text, "")

def parse_rss_and_fill():
    global rss_session
    logger.info("[RSS] Загрузка новостей через REQUESTS + FEEDPARSER...")
    
    response = None
    last_error = None
    
    # Пробуем все URL по очереди
    for url in RSS_URLS:
        try:
            logger.info(f"[RSS] Пробуем {url}...")
            response = rss_session.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            
            # Проверяем, что контент есть
            if len(response.content) < 100:
                logger.warning(f"[RSS] Пустой ответ от {url}")
                continue
                
            logger.info(f"[RSS] Успешно загружено с {url}")
            break
        except Exception as e:
            last_error = e
            logger.warning(f"[RSS] Ошибка с {url}: {e}")
            continue
    
    if not response or len(response.content) < 100:
        logger.error(f"[RSS] Все URL недоступны. Последняя ошибка: {last_error}")
        return
    
    try:
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
        logger.error(f"[RSS] Критическая ошибка парсинга: {e}")

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
                    logger.info(f"[GEO] {item['id']} -> {log_addr} -> {log_coords}")
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
    
    # Возвращаем с заголовками для отключения кэширования
    return JSONResponse(
        content=item,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@app.get("/admin/logs")
def admin_logs(password: str = Query(...)):
    """Выводит логи парсинга новостей и геокодера"""
    if password != "Zov123":
        raise HTTPException(status_code=403, detail="Неверный пароль")
    return database.get_admin_logs(limit=200)

@app.post("/admin/force-rss-update")
def force_rss_update(password: str = Query(...)):
    """Принудительно обновляет RSS-ленту"""
    if password != "Zov123":
        raise HTTPException(status_code=403, detail="Неверный пароль")
    
    try:
        # Запускаем парсинг RSS в отдельном потоке, чтобы не блокировать ответ
        import threading
        thread = threading.Thread(target=parse_rss_and_fill, daemon=True)
        thread.start()
        
        return {
            "status": "success",
            "message": "Запущено обновление RSS-ленты. Новые новости появятся в течение нескольких секунд."
        }
    except Exception as e:
        logger.error(f"[ADMIN] Ошибка при обновлении RSS: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка обновления: {str(e)}")

@app.post("/admin/news/{news_id}/reset-geocode")
def reset_geocode(news_id: int, password: str = Query(...)):
    """Сбрасывает адрес и координаты и сразу запускает геокодирование"""
    if password != "Zov123":
        raise HTTPException(status_code=403, detail="Неверный пароль")

    success = database.reset_news_geocode(news_id)
    if not success:
        raise HTTPException(status_code=404, detail="Новость не найдена")

    # Сразу запускаем геокодирование для этой новости
    try:
        item = database.force_geocode_news(news_id)
        if item:
            content = item.get("content")
            if not content or content == "Ошибка загрузки":
                content = extract_content_with_bs4(item["url"])
                # Сохраняем контент сразу
                database.update_news_content_and_coords(news_id, content, None, address=None)

            clean_content_for_geo = BeautifulSoup(content, "html.parser").get_text(separator=" ", strip=True)
            full_text = f"{item['title']} {clean_content_for_geo}"
            address, coords = extract_address_and_coords(full_text)

            # Если адрес не найден, пишем метку, чтобы не брать снова
            final_address = address if address else "NOT_FOUND"

            database.update_news_content_and_coords(news_id, content, coords, address=final_address)

            log_addr = address or 'НЕТ АДРЕСА'
            log_coords = coords or '—'
            logger.info(f"[GEO FORCE] {news_id} -> {log_addr} -> {log_coords}")

            return {
                "status": "success",
                "message": f"Геоданные для новости #{news_id} сброшены и обработаны заново.",
                "address": final_address,
                "coords": coords
            }
        else:
            raise HTTPException(status_code=404, detail="Новость не найдена после сброса")
    except Exception as e:
        logger.error(f"[GEO FORCE] Ошибка при геокодировании новости #{news_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка геокодирования: {str(e)}")

@app.post("/admin/bulk-reset-geocode")
def bulk_reset_geocode(ids: str = Query(...), password: str = Query(...)):
    """Массовый сброс геоданных для списка ID (через запятую или тире)
    
    Формат: "85,90-100,105" — сбросит новости 85, 90-100 (диапазон), 105
    """
    if password != "Zov123":
        raise HTTPException(status_code=403, detail="Неверный пароль")
    
    # Парсим строку ID
    news_ids = []
    for part in ids.split(','):
        part = part.strip()
        if '-' in part:
            # Диапазон: 90-100
            try:
                start, end = map(int, part.split('-'))
                news_ids.extend(range(start, end + 1))
            except ValueError:
                continue
        else:
            # Одиночный ID: 85
            try:
                news_ids.append(int(part))
            except ValueError:
                continue
    
    if not news_ids:
        raise HTTPException(status_code=400, detail="Неверный формат ID. Пример: 85,90-100,105")
    
    # Удаляем дубликаты и сортируем
    news_ids = sorted(set(news_ids))
    
    results = {"success": [], "not_found": [], "errors": []}
    
    for news_id in news_ids:
        try:
            # Сбрасываем
            success = database.reset_news_geocode(news_id)
            if not success:
                results["not_found"].append(news_id)
                continue
            
            # Сразу геокодируем
            item = database.force_geocode_news(news_id)
            if item:
                content = item.get("content")
                if not content or content == "Ошибка загрузки":
                    content = extract_content_with_bs4(item["url"])
                    database.update_news_content_and_coords(news_id, content, None, address=None)

                clean_content_for_geo = BeautifulSoup(content, "html.parser").get_text(separator=" ", strip=True)
                full_text = f"{item['title']} {clean_content_for_geo}"
                address, coords = extract_address_and_coords(full_text)

                final_address = address if address else "NOT_FOUND"
                database.update_news_content_and_coords(news_id, content, coords, address=final_address)

                results["success"].append({
                    "id": news_id,
                    "address": final_address,
                    "coords": coords
                })
                logger.info(f"[BULK GEO] #{news_id} -> {final_address} -> {coords}")
            else:
                results["not_found"].append(news_id)
        except Exception as e:
            results["errors"].append({"id": news_id, "error": str(e)})
            logger.error(f"[BULK GEO] Ошибка #{news_id}: {e}")
    
    return {
        "status": "success",
        "total_requested": len(news_ids),
        "processed": len(results["success"]),
        "not_found": results["not_found"],
        "errors": results["errors"],
        "results": results["success"]
    }