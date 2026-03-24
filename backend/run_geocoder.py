import time
import logging
import requests
from bs4 import BeautifulSoup

import database
from json_geocoder import SimpleGeocoder

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [WORKER] - %(message)s')
logger = logging.getLogger("GEO_WORKER")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def extract_content_with_bs4(url: str) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding 
        soup = BeautifulSoup(resp.text, 'html.parser')

        for script in soup(["script", "style"]):
            script.decompose()

        content_div = soup.find('div', class_='news-text') or soup.find('div', class_='fulltext') or soup.find('article')
        final_html = ""
        
        if content_div:
            for br in content_div.find_all("br"):
                br.replace_with("\n")
            text_content = content_div.get_text(separator="\n", strip=True)
            paragraphs = [p.strip() for p in text_content.split("\n") if len(p.strip()) > 20]
            final_html = "".join([f"<p>{p}</p>\n" for p in paragraphs])
        else:
            tags = soup.find_all('p')
            for tag in tags:
                text = tag.get_text(strip=True)
                if len(text) > 20: 
                    final_html += f"<p>{text}</p>\n"
            if not final_html:
                text = soup.get_text(separator='\n', strip=True)
                lines = [line for line in text.split('\n') if len(line) > 50]
                final_html = "".join([f"<p>{line}</p>\n" for line in lines])

        return final_html or "Текст не найден"
    except Exception as e:
        logger.error(f"Ошибка загрузки контента: {e}")
        return ""

def background_geocoder():
    logger.info("==================================================")
    logger.info("ФОНОВЫЙ ГЕОКОДЕР ЗАПУЩЕН В ОТДЕЛЬНОМ ПРОЦЕССЕ")
    logger.info("==================================================")
    
    geocoder = SimpleGeocoder()
    
    while True:
        try:
            items = database.get_uncoded_news(limit=5)
            if not items:
                # Ждем 30 секунд если нет новых новостей
                time.sleep(30)
                continue
                
            for item in items:
                try:
                    content = item.get("content")
                    if not content or content == "Ошибка загрузки":
                        content = extract_content_with_bs4(item["url"])
                    
                    if content and content != "Ошибка загрузки":
                        clean_content = BeautifulSoup(content, "html.parser").get_text(separator=" ", strip=True)
                        full_text = f"{item['title']} {clean_content}"
                        
                        address, coords = geocoder.process_text(full_text, "")
                        final_address = address if address else "NOT_FOUND"
                        
                        database.update_news_content_and_coords(item["id"], content, coords, address=final_address)
                        
                        log_addr = address or 'НЕТ АДРЕСА'
                        log_coords = coords or '—'
                        logger.info(f"Новость #{item['id']} → {log_addr} → {log_coords}")
                        
                        time.sleep(1.5) # Пауза чтобы не заспамить API Яндекса
                except Exception as e:
                    logger.error(f"Ошибка обработки ID {item.get('id')}: {e}")
                    
            time.sleep(5)
        except Exception as e:
            logger.error(f"Системная ошибка цикла: {e}")
            time.sleep(30)

if __name__ == "__main__":
    background_geocoder()
