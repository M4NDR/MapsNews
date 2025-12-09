import sqlite3
import os

# Look in backend folder
current_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_dir, '..', 'backend', 'news.db')
if not os.path.exists(db_path):
    print(f"DB file not found at {db_path}!")
else:
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        target_id = 2383
        c.execute("SELECT id, title, url FROM news WHERE id = ?", (target_id,))
        row = c.fetchone()
        
        if row:
            print(f"FOUND: ID={row[0]}")
            print(f"Title repr: {repr(row[1])}")
            url = row[2]
            print(f"URL repr: {repr(url)}")
            if '\n' in url or '\r' in url:
                print("URL contains newlines!")
        else:
            print(f"NOT FOUND: ID {target_id}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
