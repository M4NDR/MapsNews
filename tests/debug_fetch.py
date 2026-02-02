import requests
import sys

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def test_simple():
    print("Testing google.com...")
    try:
        requests.get("https://google.com", timeout=5)
        print("Google OK")
    except Exception as e:
        print(f"Google Failed: {e}")

    print("Testing news29.ru RSS...")
    try:
        resp = requests.get("https://www.news29.ru/rss", headers=HEADERS, timeout=10)
        print(f"RSS Status: {resp.status_code}")
        print(f"Content length: {len(resp.content)}")
    except Exception as e:
        print(f"RSS Failed: {e}")

if __name__ == "__main__":
    test_simple()
