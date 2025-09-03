import binascii
import json
from typing import Optional, Dict
from base64 import b64decode

# --- Configuration validation ---
def validate_config(config_base64: Optional[str]) -> Optional[Dict[str, str]]:
    if not config_base64:
        return None
    
    try:
        # --- Validate base64 ---
        decoded_bytes = b64decode(config_base64, validate=True)
        decoded_str = decoded_bytes.decode('utf-8')
        
        # --- Validate JSON ---
        config_dict = json.loads(decoded_str)
        
        # --- Check structure ---
        if not isinstance(config_dict, dict):
            return None
            
        # --- Check required keys ---
        if "alldebrid" not in config_dict or "tmdb" not in config_dict:
            return None
            
        # --- Check keys not empty ---
        if not config_dict["alldebrid"] or not config_dict["tmdb"]:
            return None
        
        # --- Validate excluded_words ---
        if "excluded_words" in config_dict:
            excluded_words = config_dict["excluded_words"]
            if not isinstance(excluded_words, list):
                return None
            
            for word in excluded_words:
                if not isinstance(word, str):
                    return None
        else:
            config_dict["excluded_words"] = []
            
        return config_dict
        
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError):
        return None

# --- Media info extraction ---
def extract_media_info(content_id: str, content_type: str) -> Dict[str, Optional[str]]:
    content_id_formatted = content_id.replace(".json", "")
    
    if content_type == "series" and ":" in content_id_formatted:
        parts = content_id_formatted.split(":")
        return {
            "imdb_id": parts[0],
            "season": parts[1] if len(parts) > 1 else "1",
            "episode": parts[2] if len(parts) > 2 else "1"
        }
    
    return {
        "imdb_id": content_id_formatted,
        "season": None,
        "episode": None
    }