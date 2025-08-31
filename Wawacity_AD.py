from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from urllib.parse import quote_plus
from typing import Optional, Dict
from os import environ
from httpx import AsyncClient
from asyncio import get_event_loop, get_running_loop, sleep
from search import search_movie
import base64
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PORT = int(environ.get("PORT", "7000"))
PROXY_URL = environ.get("PROXY_URL")

app.mount("/static", StaticFiles(directory="public"), name="public")

ADDON_MANIFEST = {
    "id": "wawacity.ad",
    "version": "1.1.1",
    "name": "Wawacity AD",
    "description": "Accès au contenu de Wawacity via Stremio & AllDebrid (non officiel)",
    "catalogs": [],
    "resources": ["stream"],
    "types": ["movie"],
    "idPrefixes": ["tt"],
    "behaviorHints": {
        "configurable": True
    },
    "logo": "https://i.imgur.com/y9riTDE.png",
    "background": "https://i.imgur.com/eQRsbJx.jpeg"
}

def parse_config_base64(config_base64: str) -> Dict[str, str]:
    """Decode base64 config and return dictionary with keys."""
    try:
        decoded_json = base64.b64decode(config_base64).decode('utf-8')
        config_dict = json.loads(decoded_json)
        return config_dict
    except Exception as e:
        print(f"[ERROR] Failed to decode base64 config: {e}")
        return {}

def get_key_from_config(config_base64: str, key_name: str) -> str:
    """Extract key from base64 encoded config."""
    if not config_base64:
        return ""
    config_dict = parse_config_base64(config_base64)
    return config_dict.get(key_name, "")

@app.get("/")
async def root():
    return RedirectResponse("/configure")

@app.get("/configure", response_class=HTMLResponse)
async def configure():
    return FileResponse("public/index.html")

@app.get("/{b64config}/configure", response_class=HTMLResponse)
async def configure_addon(request: Request, b64config: str):
    return FileResponse("public/index.html")

# --- Manifest route ---
@app.get("/{b64config}/manifest.json")
async def get_manifest_with_config(b64config: str):
    return JSONResponse(content=ADDON_MANIFEST)


# --- Stream routes ---
@app.get("/{b64config}/stream/{content_type}/{content_id}")
async def get_streams_with_config(request: Request, b64config: str, content_type: str, content_id: str):
    return await handle_streams(request, content_type, content_id, b64config=b64config)


# --- Handle streams ---
async def handle_streams(request: Request, content_type: str, content_id: str, b64config: Optional[str]):
    content_id_formatted = content_id.replace(".json", "")
    print(f"[DEBUG] Search for streams: {content_type}/{content_id_formatted}")

    ad_key = get_key_from_config(b64config, "alldebrid")
    tmdb_key = get_key_from_config(b64config, "tmdb")

    metadata = await get_movie_metadata(content_id_formatted, tmdb_key)
    if not metadata:
        print(f"[DEBUG] No metadata for {content_id_formatted}")
        return JSONResponse(content={"streams": []})

    title = metadata.get("title", "")
    year = metadata.get("year")
    print(f"[DEBUG] Searching: {title} ({year})")

    results = await call_search_script(title, year)
    if not results:
        print(f"[DEBUG] No links found for {title}")
        return JSONResponse(content={"streams": []})

    streams = []
    for res in results:
        dl_link = res.get("dl_protect")
        if not dl_link:
            continue
        quality = res.get("quality", "?")
        language = res.get("language", "?")
        size = res.get("size", "?")
        original_name = res.get("original_name", "?")

        base_url = str(request.base_url).rstrip('/')
        q_link = quote_plus(dl_link)
        q_b64config = quote_plus(b64config) if b64config else ''
        playback_url = f"{base_url}/resolve?link={q_link}&b64config={q_b64config}"

        streams.append({
            "name": f"[Wawacity 🌇] {quality}",
            "description": f"{title}\r\n🌐 {language}\r\n🎞️ {quality}\r\n📦 {size} 📅 {year}\r\n📁 {original_name}",
            "url": playback_url
        })

    print(f"[DEBUG] Return {len(streams)} stream(s)")
    return JSONResponse(content={"streams": streams, "cacheMaxAge": 1})


# --- Metadata TMDB ---
async def get_movie_metadata(imdb_id: str, tmdb_key: str) -> Optional[dict]:
    url = f"https://api.themoviedb.org/3/find/{imdb_id}?external_source=imdb_id"
    headers = {
        "Authorization": f"Bearer {tmdb_key}",
        "Content-Type": "application/json",
    }
    try:
        proxy_config = {"proxy": PROXY_URL} if PROXY_URL else {}
        async with AsyncClient(**proxy_config) as client:
            response = await client.get(url, headers=headers, timeout=10)
            data = response.json()
        
        if response.status_code == 200 and data.get("movie_results"):
            movie = data["movie_results"][0]
            title = movie["original_title"] if movie.get("original_language") == "fr" else movie["title"]
            year = movie.get("release_date", "").split("-")[0]
            return {"title": title, "year": year}
        return None
    except Exception as e:
        print(f"[ERROR] get_movie_metadata failed: {e}")
        return None


# --- Call search script ---
async def call_search_script(title: str, year: str = None) -> list:
    try:
        try:
            loop = get_running_loop()
        except RuntimeError:
            loop = get_event_loop()
        results = await loop.run_in_executor(None, lambda: search_movie(title, year))
        return results or []
    except Exception as e:
        print(f"[ERROR] search_movie failed: {e}")
        return []


# --- AllDebrid resolution ---
@app.get("/resolve")
async def resolve(link: str, b64config: str):
    apikey = get_key_from_config(b64config, "alldebrid")
    direct = await convert_to_alldebrid(link, apikey)
    
    if direct and direct != "LINK_DOWN":
        return RedirectResponse(url=direct, status_code=302)
    elif direct == "LINK_DOWN":
        return FileResponse("public/link_down_error.mkv")
    else:
        return FileResponse("public/error.mkv")


async def convert_to_alldebrid(dl_protect_link: str, apikey: str, max_retries: int = 8) -> Optional[str]:
    if not apikey:
        print("[ERROR] No AllDebrid API key provided")
        return None

    for attempt in range(max_retries):
        try:
            proxy_config = {"proxy": PROXY_URL} if PROXY_URL else {}
            async with AsyncClient(timeout=15, **proxy_config) as client:
                r1 = await client.get(
                    "https://apislow.alldebrid.com/v4/link/redirector",
                    params={
                        "agent": "Wawacity AD",
                        "apikey": apikey,
                        "link": dl_protect_link
                    }
                )
                r1.raise_for_status()
                result1 = r1.json()
                
                if result1.get("status") != "success":
                    error_code = result1.get("error", {}).get("code")
                    if attempt < max_retries - 1:
                        print(f"[WARN] API error {error_code}, retry {attempt + 1}/{max_retries} in 2s")
                        await sleep(2)
                        continue
                    else:
                        print(f"[ERROR] API failed after {max_retries} attempts: {result1}")
                        return None
                
                redirect_link = result1["data"]["links"][0]
                
                r2 = await client.get(
                    "https://apislow.alldebrid.com/v4/link/unlock",
                    params={
                        "agent": "Wawacity AD",
                        "apikey": apikey,
                        "link": redirect_link
                    }
                )
                r2.raise_for_status()
                result2 = r2.json()

                if result2.get("error", {}).get("code") == "LINK_DOWN":
                    print(f"[INFO] Lien mort détecté pour {dl_protect_link}")
                    return "LINK_DOWN"

                if result2.get("status") == "success" and result2["data"].get("link"):
                    if attempt > 0:
                        print(f"[INFO] Retry successful on attempt {attempt + 1}")
                    return result2["data"]["link"]

                if attempt < max_retries - 1:
                    print(f"[WARN] Unlock failed, retry {attempt + 1}/{max_retries} in 2s: {result2}")
                    await sleep(2)
                    continue
                else:
                    print(f"[ERROR] Unlock failed after {max_retries} attempts: {result2}")
                    return None

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[WARN] Exception {type(e).__name__}: {e}, retry {attempt + 1}/{max_retries} in 2s")
                await sleep(2)
                continue
            else:
                print(f"[ERROR] Exception after {max_retries} attempts: {type(e).__name__}: {e}")
                return None
    
    return None


# --- Debug endpoints ---
@app.get("/debug/test-search")
async def debug_search(title: str, year: str = None):
    results = await call_search_script(title, year)
    return {"title": title, "year": year, "results": results}

@app.get("/debug/test-alldebrid")
async def debug_alldebrid(link: str, apikey: str):
    result = await convert_to_alldebrid(link, apikey=apikey)
    return {"input_link": link, "alldebrid_link": result}


# --- Run ---
if __name__ == "__main__":
    import uvicorn
    print("🚀 Lancement de l'addon Stremio Wawacity")
    print(f"🏠 Interface web: http://localhost:{PORT}/")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
