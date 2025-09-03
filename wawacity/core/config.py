from os import environ
from typing import Optional
from dotenv import load_dotenv

# --- Environment variables loading ---
load_dotenv()

# --- Addon customization ---
ADDON_ID = environ.get("ADDON_ID", "wawacity.ad")
ADDON_NAME = environ.get("ADDON_NAME", "Wawacity AD")

# --- Server configuration ---
PORT = int(environ.get("PORT", "7000"))

# --- Source configuration ---
WAWACITY_URL = environ.get("WAWACITY_URL", "https://wawacity.diy")

# --- Database configuration ---
DATABASE_VERSION = "1.0"
DATABASE_TYPE = environ.get("DATABASE_TYPE", "sqlite").lower()
DATABASE_PATH = environ.get("DATABASE_PATH", "/app/data/wawacity-addon.db")
DATABASE_URL = environ.get("DATABASE_URL", "")

# --- Cache configuration ---
CONTENT_CACHE_TTL = int(environ.get("CONTENT_CACHE_TTL", "3600"))  # 1 hour - Movies and series
DEAD_LINK_TTL = int(environ.get("DEAD_LINK_TTL", "604800"))  # 7 days - Dead links tracking

# --- Lock configuration ---
SCRAPE_LOCK_TTL = int(environ.get("SCRAPE_LOCK_TTL", "300"))  # 5 minutes - Scraping lock duration
SCRAPE_WAIT_TIMEOUT = int(environ.get("SCRAPE_WAIT_TIMEOUT", "30"))  # 30 seconds - Lock wait timeout

# --- AllDebrid configuration ---
ALLDEBRID_MAX_RETRIES = int(environ.get("ALLDEBRID_MAX_RETRIES", "10"))
RETRY_DELAY_SECONDS = int(environ.get("RETRY_DELAY_SECONDS", "2"))
ALLDEBRID_API_URL = "https://apislow.alldebrid.com/v4"

# --- TMDB configuration ---
TMDB_API_URL = "https://api.themoviedb.org/3"

# --- Interface customization ---
CUSTOM_HTML = environ.get("CUSTOM_HTML", "")

# --- Security configuration ---
ADDON_PASSWORD = environ.get("ADDON_PASSWORD", "")

# --- Proxy configuration ---
PROXY_URL = environ.get("PROXY_URL")

# --- Internal configuration ---
CLEANUP_INTERVAL = 60  # 60 seconds cleanup cycle

# --- Stremio addon manifest ---
ADDON_MANIFEST = {
    "id": ADDON_ID,
    "name": ADDON_NAME,
    "version": "2.0.1",
    "description": "Accès au contenu de Wawacity via Stremio & AllDebrid (non officiel)",
    "catalogs": [],
    "resources": ["stream"],
    "types": ["movie", "series"],
    "idPrefixes": ["tt"],
    "behaviorHints": {
        "configurable": True
    },
    "logo": "https://i.imgur.com/y9riTDE.png",
    "background": "https://i.imgur.com/eQRsbJx.jpeg"
}

# --- Database URL builder ---
def get_database_url() -> str:
    if DATABASE_TYPE == "sqlite":
        return f"sqlite:///{DATABASE_PATH}"
    return f"postgresql://{DATABASE_URL}"
