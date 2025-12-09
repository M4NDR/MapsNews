import os
import json
import requests
import time
from typing import List, Dict, Optional, Tuple
from natasha import (
    Segmenter,
    MorphVocab,
    AddrExtractor,
    Doc
)

# === CONFIGURATION ===
# Replace with your actual key or set environment variable
YANDEX_API_KEY = os.getenv("GEOCODER_API_KEY", "686e5b6d-df4e-49de-a918-317aa589c34c")
CACHE_FILE = "geo_cache.json"

class AdvancedGeocoder:
    def __init__(self, api_key: str = YANDEX_API_KEY):
        self.api_key = api_key
        
        # Initialize Natasha components
        self.segmenter = Segmenter()
        self.morph_vocab = MorphVocab()
        self.addr_extractor = AddrExtractor(self.morph_vocab)
        
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[CACHE] Error loading cache: {e}")
                return {}
        return {}

    def _save_cache(self):
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CACHE] Error saving cache: {e}")

    def extract_raw_addresses(self, text: str) -> List[Tuple[str, str]]:
        """
        Extracts addresses from text using Natasha.
        Returns list of tuples: (original_text_fragment, normalized_address_string)
        """
        doc = Doc(text)
        doc.segment(self.segmenter)
        
        # Natasha address extraction
        matches = list(self.addr_extractor(text)) # Consume generator
        print(f"[DEBUG] Raw matches count: {len(matches)}")
        
        results = []
        for match in matches:
            print(f"[DEBUG] Match fact: {match.fact}")
            start, stop = match.start, match.stop
            original_fragment = text[start:stop]
            
            # Normalize the address parts
            parts = match.fact
            normalized_parts = []
            
            # Order matters for geocoding usually (City, Street, Number)
            # Natasha returns simple parts structure
            if parts.type: normalized_parts.append(parts.type)
            if parts.value: normalized_parts.append(parts.value)
            
            # For this example, we'll construct a simple string. 
            # In a real app, you might want to map fields (street, house, etc)
            # Natasha's 'fact' object has fields like 'street', 'house', 'number' depending on extraction
            
            # Let's try to reconstruct a clean string from the structured fact
            norm_str = ""
            # Simple heuristic: flatten the fact object
            # Note: parts is an object like Addr(parts=[...]) or simple depending on version.
            # Usually match.fact is an object.
            
            # Since we want something ready-to-run, let's just use the original fragment 
            # or try to interpret parts. For simplicity and robustness with Natasha:
            # We can rely on the original fragment for yandex often, or normalize using morph_vocab if needed.
            # But let's build a clean string: "type value"
            
            # Better approach: Just use original fragment for geocoding but refined
            # Or manually assemble:
            addr_str_parts = []
            for attr in ['region', 'city', 'street', 'building']:
                val = getattr(parts, attr, None)
                if val:
                    # Some tricky logic might be needed here if 'val' is not just a string
                    # But often it is just text.
                    pass
            
            # Fallback: straightforward normalization of the match
            # match.fact.normalize(self.morph_vocab) # Removed due to AttributeError
            
            # Construct string from parts
            # This relies on the structure of match.fact (Addr)
            normalized_address = self._addr_to_string(match.fact)
            
            if normalized_address:
                results.append((original_fragment, normalized_address))
                
        return results

    def _addr_to_string(self, fact) -> str:
        """Converts Natasha Addr fact to string"""
        parts = []
        
        # Handle AddrPart (single component)
        if type(fact).__name__ == 'AddrPart':
             type_str = fact.type if fact.type else ""
             return f"{type_str} {fact.value}".strip()
             
        # Handle Addr (composite)
        if hasattr(fact, 'region') and fact.region: parts.append(fact.region)
        if hasattr(fact, 'city') and fact.city: parts.append(fact.city)
        if hasattr(fact, 'street') and fact.street: parts.append(fact.street)
        if hasattr(fact, 'building') and fact.building: parts.append(fact.building)
        if hasattr(fact, 'room') and fact.room: parts.append(fact.room)
        
        # If composite yielded nothing, maybe it has parts list? 
        if not parts and hasattr(fact, 'parts'):
            # Some versions use a list of parts
            return " ".join([f"{p.type} {p.value}" for p in fact.parts])
            
        return ", ".join(parts) if parts else ""

    def geocode(self, address: str) -> Optional[List[float]]:
        """
        Geocodes the address string using Yandex. 
        Returns [lat, lon] or None.
        Uses caching.
        """
        if not address: return None
        
        # Check cache
        if address in self.cache:
            print(f"[CACHE] Hit for '{address}'")
            return self.cache[address]

        # Request Yandex
        try:
            full_query = f"Архангельская область, {address}" # Context bias
            url = "https://geocode-maps.yandex.ru/1.x/"
            params = {
                "apikey": self.api_key,
                "geocode": full_query,
                "format": "json",
                "results": 1
            }
            
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                geo_object = data["response"]["GeoObjectCollection"]["featureMember"]
                
                if geo_object:
                    pos = geo_object[0]["GeoObject"]["Point"]["pos"]
                    lon, lat = map(float, pos.split())
                    result = [lat, lon]
                    
                    # Store in cache
                    self.cache[address] = result
                    self._save_cache()
                    time.sleep(0.1) # Rate limit respect
                    return result
            else:
                print(f"[YANDEX] Error {response.status_code}")

        except Exception as e:
            print(f"[YANDEX] Exception: {e}")
            
        return None

    def process_text(self, text: str) -> List[Dict]:
        """
        Main pipeline: Extract -> Geocode -> Result List
        """
        print(f"--- Processing Text ---")
        extracted = self.extract_raw_addresses(text)
        results = []
        
        for orig, norm in extracted:
            if not norm: continue
            
            # Skip short garbage
            if len(norm) < 5: continue
            
            print(f"Found: '{orig}' -> Norm: '{norm}'")
            coords = self.geocode(norm)
            
            if coords:
                print(f"  -> Coords: {coords}")
                results.append({
                    "original": orig,
                    "normalized": norm,
                    "coords": coords
                })
            else:
                print(f"  -> Coords not found")
        
        return results

# === DEMO RUN ===
if __name__ == "__main__":
    # Test text
    sample_text = """
    В Архангельске на улице Ленина, дом 5 произошла авария. 
    Потом скорая поехала в 3-ю поликлинику на улице Победы.
    Также сообщают о пробках на пересечении Троицкого и Садовой.
    """
    
    geocoder = AdvancedGeocoder()
    
    # 1. Ensure Natasha is fine (it might need download mainly for embeddings if used, 
    # but AddrExtractor uses rule-based morphology usually included)
    
    results = geocoder.process_text(sample_text)
    
    print("\n=== FINAL RESULTS ===")
    print(json.dumps(results, indent=2, ensure_ascii=False))
