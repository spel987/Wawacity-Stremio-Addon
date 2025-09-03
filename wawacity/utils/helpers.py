import json
from typing import Optional, Dict, Any
from urllib.parse import quote_plus, urlparse, parse_qs, unquote
from base64 import b64encode, b64decode

# --- Base64 encoding ---
def encode_config_to_base64(config: Dict[str, Any]) -> str:
    return b64encode(json.dumps(config).encode()).decode()

# --- Cache key creation ---
def create_cache_key(cache_type: str, title: str, year: Optional[str] = None) -> str:
    cache_key = f"{cache_type}:{quote_plus(title.lower())}"
    if year:
        cache_key += f":{year}"
    return cache_key

# --- Filename extraction from dl-protect links ---
def extract_filename_from_link(url: str, link_text: str) -> str:
    # --- First try from link text ---
    original_filename = link_text.split(":")[-1].strip() if ":" in link_text else link_text.strip()
    
    # --- Then try decoding from URL ---
    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        fn_encoded = query_params.get('fn', [None])[0]
        
        if fn_encoded:
            fn_unquoted = unquote(fn_encoded)
            decoded_fn = b64decode(fn_unquoted).decode('utf-8')
            return decoded_fn if decoded_fn else original_filename
    except Exception:
        pass
    
    return original_filename

# --- URL formatting ---
def format_url(url: str, base_url: str) -> str:
    if not url:
        return ""
    
    if url.startswith("http://") or url.startswith("https://"):
        return url
    
    if url.startswith("/"):
        return f"{base_url}{url}"
    
    return url

# --- URL parameter encoding ---
def quote_url_param(param: str) -> str:
    return quote_plus(param)