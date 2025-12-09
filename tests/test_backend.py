import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), '..', 'backend'))

try:
    import database
    import main
    print("Imports successful")
    
    # Test database connection and query
    database.init_db()
    print("DB Init successful")
    
    count = database.get_news_count()
    print(f"News count: {count}")
    
    # Test get_all_news
    items = database.get_all_news(limit=5)
    print(f"Fetched {len(items)} items using get_all_news")
    if items:
        print(f"First item: {items[0]['title']}")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
