# backend/database.py
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional

DB_PATH = "news.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            old_id INTEGER,  -- ← НОВОЕ ПОЛЕ: старый ID из RSS
            url TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            preview TEXT,
            date TEXT NOT NULL,
            source TEXT DEFAULT 'news29.ru',
            image TEXT,
            category TEXT DEFAULT 'другое',
            content TEXT,
            coords TEXT
        )
    """)
    # Добавляем колонку old_id, если её нет (для совместимости)
    try:
        cursor.execute("ALTER TABLE news ADD COLUMN old_id INTEGER")
    except sqlite3.OperationalError:
        pass  # уже есть
    conn.commit()
    conn.close()

def insert_or_update_news(news_data: Dict, old_id: Optional[int] = None) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO news 
        (old_id, url, title, preview, date, source, image, category, content, coords)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        old_id,
        news_data['url'],
        news_data['title'],
        news_data['preview'],
        news_data['date'],
        news_data.get('source', 'news29.ru'),
        news_data.get('image'),
        news_data.get('category', 'другое'),
        news_data.get('content'),
        json.dumps(news_data.get('coords')) if news_data.get('coords') else None
    ))
    conn.commit()
    conn.close()
    return cursor.lastrowid

def get_all_news(category: Optional[str] = None, limit: int = 200) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = """
        SELECT id, old_id, title, preview, date, source, image, category
        FROM news
        WHERE date >= '2025-10-01'
    """
    params = []

    if category and category.lower() != "все":
        query += " AND category = ?"
        params.append(category.lower())

    query += " ORDER BY date DESC, id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    result = []
    for row in rows:
        db_id, old_id, title, preview, date, source, image, category = row
        result.append({
            "id": old_id if old_id is not None else db_id,  # ← ВАЖНО: возвращаем old_id!
            "title": title,
            "preview": preview,
            "date": date,
            "source": source,
            "image": image,
            "category": category
        })
    return result

def get_news_by_old_id(old_id: int) -> Optional[Dict]:
    """Находим новость по СТАРОМУ ID из RSS"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM news WHERE old_id = ?", (old_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    # row: id, old_id, url, title, ...
    coords = json.loads(row[10]) if row[10] else None
    return {
        "id": row[1],  # old_id
        "url": row[2],
        "title": row[3],
        "preview": row[4],
        "date": row[5],
        "source": row[6],
        "image": row[7],
        "category": row[8],
        "content": row[9],
        "coords": coords
    }

def get_news_by_db_id(db_id: int) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM news WHERE id = ?", (db_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    coords = json.loads(row[10]) if row[10] else None
    return {
        "id": row[1] if row[1] else row[0],
        "url": row[2],
        "title": row[3],
        "content": row[9],
        "coords": coords
    }