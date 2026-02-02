import sys
import os
import requests
import trafilatura
from bs4 import BeautifulSoup
import re
import json
import sqlite3 # Added import

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.join(current_dir, '..', 'backend')
sys.path.append(backend_path)

try:
    import database
    print("Imports successful")
    
    # Init DB
    database.init_db()
    
    # Check if ID 2383 exists (from screenshot)
    target_id = 2383
    item = database.get_news_by_id(target_id)
    
    if not item:
        print(f"News with ID {target_id} NOT FOUND in DB.")
        # Let's list some valid IDs
        conn = sqlite3.connect("news.db")
        c = conn.cursor()
        c.execute("SELECT id FROM news ORDER BY id DESC LIMIT 5")
        ids = c.fetchall()
        print(f"Latest IDs in DB: {ids}")
        conn.close()
    else:
        print(f"News found: {item['title']}")
        print(f"URL: {item['url']}")
        
        # Try to simulate the parsing logic from main.py
        HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            print("Attempting to fetch URL...")
            resp = requests.get(item["url"], headers=HEADERS, timeout=10)
            print(f"Response status: {resp.status_code}")
            
            if resp.status_code == 200:
                html = resp.text
                text = trafilatura.extract(html)
                if text:
                    print("Trafilatura extraction successful")
                    print(f"Content length: {len(text)}")
                else:
                    print("Trafilatura returned None")
            else:
                print("Failed to fetch URL")
                
        except Exception as e:
            print(f"Error during parsing: {e}")

except Exception as e:
    print(f"General Error: {e}")
    import traceback
    traceback.print_exc()
