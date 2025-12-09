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
            old_id INTEGER,
            url TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            preview TEXT,
            date TEXT NOT NULL,
            source TEXT DEFAULT 'news29.ru',
            image TEXT,
            category TEXT DEFAULT 'другое',
            content TEXT,
            coords TEXT,
            address TEXT
        )
    """)
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON news (date DESC)')
    
    # Миграция
    try:
        cursor.execute("ALTER TABLE news ADD COLUMN old_id INTEGER")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE news ADD COLUMN address TEXT")
    except:
        pass

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
            (url, title, preview, date, source, image, category, content, coords, old_id, address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            data.get("old_id"),
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
    
    query = "SELECT id, title, url, preview, date, source, image, category FROM news"
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
            "date": r[4], "source": r[5], "image": r[6], "category": r[7]
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
    cursor.execute("SELECT * FROM news WHERE id = ?", (news_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
        
    return {
        "id": row[0],
        "url": row[2],
        "title": row[3],
        "date": row[5],
        "source": row[6],
        "image": row[7],
        "category": row[8],
        "content": row[9],
        "coords": json.loads(row[10]) if row[10] else None,
        "address": row[11] if len(row) > 11 else None
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
    
    # Если передан адрес, обновляем и его. Если нет — не трогаем.
    if address:
        c.execute("""
            UPDATE news 
            SET content = ?, coords = ?, address = ?
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