import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional

DB_PATH = "news.db"

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            preview TEXT,
            date TEXT NOT NULL,
            source TEXT DEFAULT 'news29.ru',
            image TEXT,
            category TEXT DEFAULT 'другое',
            content TEXT,
            coords TEXT,
            address TEXT,
            parsed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            geocoded_at DATETIME
        )
    """)
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON news (date DESC)')
    
    try: cursor.execute("ALTER TABLE news ADD COLUMN parsed_at DATETIME")
    except Exception: pass
    try: cursor.execute("ALTER TABLE news ADD COLUMN geocoded_at DATETIME")
    except Exception: pass

    conn.commit()
    conn.close()
    logger.info(f"БД инициализирована: {DB_PATH}")

def save_news(data: Dict, content: str = None, coords: list = None, address: str = None) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Используем INSERT OR IGNORE, чтобы не перезаписывать существующие новости
        # и не менять их ID (что сбрасывало бы результаты геокодера)
        cursor.execute("""
            INSERT OR IGNORE INTO news 
            (url, title, preview, date, source, image, category, content, coords, address, parsed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            data["url"], 
            data["title"], 
            data["preview"], 
            data["date"],
            data.get("source", "news29.ru"), 
            data.get("image"), 
            data.get("category", "другое"),
            content, 
            json.dumps(coords) if coords else None,
            address
        ))
        
        # Если строка была вставлена, rowcount будет 1. Если проигнорирована - 0.
        if cursor.rowcount > 0:
            conn.commit()
            conn.close()
            return True
        else:
            conn.close()
            return False
    except Exception as e:
        logger.error(f"Ошибка сохранения новости {data.get('url')}: {e}")
        return False

def get_all_news(limit: int = 200, category: str = None) -> List[Dict]:
    """Возвращает список новостей для клиентской пагинации"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = "SELECT id, title, url, preview, date, source, image, category, coords FROM news"
    params = []
    
    if category and category.lower() != "все":
        query += " WHERE category = ?"
        params.append(category.lower())

    query += " ORDER BY date DESC, id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": r[0], "title": r[1], "url": r[2], "preview": r[3], 
            "date": r[4], "source": r[5], "image": r[6], "category": r[7],
            "coords": json.loads(r[8]) if r[8] else None
        } 
        for r in rows
    ]

def get_news_count() -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM news")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_news_by_id(news_id: int) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, url, title, date, source, image, category, content, coords, address 
        FROM news WHERE id = ?
    """, (news_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
        
    return {
        "id": row[0],
        "url": row[1],
        "title": row[2],
        "date": row[3],
        "source": row[4],
        "image": row[5],
        "category": row[6],
        "content": row[7],
        "coords": json.loads(row[8]) if row[8] else None,
        "address": row[9] if len(row) > 9 else None
    }

def get_uncoded_news(limit=10):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Check if 'address' column exists (it should, but just in case)
    # We select news where Coords are NULL AND Address is NULL (we haven't tried yet)
    # This prevents looping over items that we already processed but found nothing (Address="Архангельск", Coords=None)
    c.execute("SELECT * FROM news WHERE coords IS NULL AND (address IS NULL OR address = '') ORDER BY date DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_news_content_and_coords(news_id, content, coords, address=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    coords_json = json.dumps(coords) if coords else None
    
    # Если передан адрес, обновляем и его. И ставим время геокодирования
    if address:
        c.execute("""
            UPDATE news 
            SET content = ?, coords = ?, address = ?, geocoded_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (content, coords_json, address, news_id))
    else:
        c.execute("""
            UPDATE news 
            SET content = ?, coords = ?
            WHERE id = ?
        """, (content, coords_json, news_id))
    conn.commit()
    conn.close()

def get_admin_logs(limit=200):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, title, address, parsed_at, geocoded_at FROM news ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def reset_news_geocode(news_id: int) -> bool:
    """Очищает данные геокодирования для новости, заставляя парсер искать координаты заново"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Сбрасываем address в NULL (не в пустую строку!), чтобы геокодер снова обработал новость
    # Также сбрасываем coords и geocoded_at
    cursor.execute("""
        UPDATE news
        SET address = NULL, coords = NULL, geocoded_at = NULL
        WHERE id = ?
    """, (news_id,))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def get_uncoded_news(limit=10):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Выбираем новости, где координаты не найдены И адрес ещё не установлен (NULL)
    # Это включает новости, которые никогда не обрабатывались, и новости после сброса
    # NOT_FOUND означает что геокодер уже искал и ничего не нашел - такие новости не берем
    c.execute("SELECT * FROM news WHERE coords IS NULL AND address IS NULL ORDER BY date DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def force_geocode_news(news_id: int):
    """Принудительно запускает геокодирование для конкретной новости"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM news WHERE id = ?", (news_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return None
    
    item = dict(row)
    return item