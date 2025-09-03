from fastapi import APIRouter, Request, Query, Path
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse, HTMLResponse
from typing import Optional

from wawacity.core.config import ADDON_MANIFEST, WAWACITY_URL, PROXY_URL, CUSTOM_HTML, ADDON_PASSWORD
from wawacity.utils.validators import validate_config
from wawacity.services.stream import stream_service
from wawacity.services.alldebrid import alldebrid_service
from wawacity.scrapers.movie import movie_scraper
from wawacity.scrapers.series import series_scraper
from wawacity.utils.logger import logger

router = APIRouter()

# --- Main routes ---
@router.get("/", summary="Accueil", description="Redirection automatique vers la page de configuration")
async def root():
    return RedirectResponse("/configure")

@router.get("/configure", summary="Configuration", description="Interface web pour configurer vos clés API AllDebrid et TMDB")
async def configure():
    with open("wawacity/public/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    
    html_content = html_content.replace("{{CUSTOM_HTML}}", CUSTOM_HTML)
    
    return HTMLResponse(content=html_content)

@router.get("/{b64config}/configure", summary="Reconfigurer", description="Modifier la configuration existante avec vos nouvelles clés API")
async def configure_addon(
    b64config: str = Path(..., description="Configuration encodée (base64) avec clés API AllDebrid/TMDB")
):
    with open("wawacity/public/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    
    html_content = html_content.replace("{{CUSTOM_HTML}}", CUSTOM_HTML)
    
    return HTMLResponse(content=html_content)

# --- Manifest route ---
@router.get("/{b64config}/manifest.json", summary="Manifest Stremio", description="Informations de l'addon pour l'installation dans Stremio")
async def get_manifest(
    b64config: str = Path(..., description="Configuration encodée (base64) avec clés API AllDebrid/TMDB")
):
    return JSONResponse(content=ADDON_MANIFEST)

# --- Streaming routes ---
@router.get("/{b64config}/stream/{content_type}/{content_id}", 
           summary="Rechercher des streams", 
           description="Trouve et retourne les liens de streaming pour un film ou une série depuis Wawacity")
async def get_streams(
    request: Request,
    b64config: str = Path(..., description="Configuration encodée (base64) avec clés API AllDebrid/TMDB"),
    content_type: str = Path(..., description="Type de contenu: 'movie' ou 'series'"),
    content_id: str = Path(..., description="ID IMDB (films) ou IMDB:saison:episode (séries)")
):
    config = validate_config(b64config)
    if not config:
        logger.error("Invalid configuration - Check format or missing/empty keys")
        return JSONResponse(content={"streams": []})
    
    content_id_formatted = content_id.replace(".json", "")
    logger.log("API", f"Stream request: {content_type}/{content_id_formatted}")
    
    try:
        base_url = str(request.base_url).rstrip('/')
        
        streams = await stream_service.get_streams(
            content_type=content_type,
            content_id=content_id_formatted,
            config=config,
            base_url=base_url
        )
        
        return JSONResponse(content={
            "streams": streams,
            "cacheMaxAge": 1
        })
        
    except Exception as e:
        logger.error(f"Stream request failed: {e}")
        return JSONResponse(content={"streams": []})

# --- AllDebrid resolution route ---
@router.get("/resolve", 
           summary="Résoudre un lien", 
           description="Convertit un lien dl-protect en lien direct via AllDebrid pour le streaming")
async def resolve(
    link: str = Query(..., description="Lien dl-protect à convertir (ex: https://dl-protect.link/abc123)"),
    b64config: str = Query(..., description="Configuration encodée contenant votre clé API AllDebrid")
):
    config = validate_config(b64config)
    if not config:
        return FileResponse("wawacity/public/error.mkv")
    
    apikey = config.get("alldebrid", "")
    if not apikey:
        return FileResponse("wawacity/public/error.mkv")
    
    direct_link = await stream_service.resolve_link(link, apikey)
    
    if direct_link and direct_link != "LINK_DOWN":
        return RedirectResponse(url=direct_link, status_code=302)
    elif direct_link == "LINK_DOWN":
        return FileResponse("wawacity/public/link_down_error.mkv")
    else:
        return FileResponse("wawacity/public/error.mkv")

# --- Debug routes ---
@router.get("/debug/test-search", 
           summary="Test de recherche", 
           description="Teste la recherche Wawacity directement")
async def debug_search(
    title: str = Query(..., description="Titre du film ou série à rechercher"),
    year: Optional[str] = Query(None, description="Année de sortie (optionnel)"),
    type: str = Query("film", description="Type de contenu: 'film' ou 'serie'")
):
    try:
        if type == "serie":
            results = await series_scraper.search(title, year)
        else:
            results = await movie_scraper.search(title, year)
        
        return {
            "title": title,
            "year": year,
            "type": type,
            "count": len(results),
            "results": results
        }
    except Exception as e:
        return {
            "error": str(e),
            "title": title,
            "year": year,
            "type": type
        }

@router.get("/debug/test-alldebrid", 
           summary="Test AllDebrid", 
           description="Teste la conversion d'un lien dl-protect via votre clé AllDebrid")
async def debug_alldebrid(
    link: str = Query(..., description="Lien dl-protect à convertir (ex: https://dl-protect.link/abc123)"),
    apikey: str = Query(..., description="Clé API AllDebrid")
):
    try:
        result = await alldebrid_service.convert_link(link, apikey)
        return {
            "input_link": link,
            "alldebrid_link": result,
            "status": "success" if result and result != "LINK_DOWN" else "failed"
        }
    except Exception as e:
        return {
            "input_link": link,
            "error": str(e),
            "status": "error"
        }

# --- Health check ---
@router.get("/health", 
           summary="État de santé", 
           description="Teste l'état du serveur, de Wawacity, de la base de données et du proxy")
async def health_check():
    import time
    from wawacity.utils.http_client import http_client
    from wawacity.utils.database import database
    
    start_time = time.time()
    health_status = {
        "status": "healthy",
        "version": ADDON_MANIFEST["version"],
        "timestamp": int(time.time()),
        "checks": {}
    }
    
    # --- Server test ---
    health_status["checks"]["server"] = {
        "status": "ok",
        "message": "Addon server running"
    }
    
    # --- Database test ---
    try:
        await database.fetch_val("SELECT 1")
        health_status["checks"]["database"] = {
            "status": "ok",
            "message": "Database connection active"
        }
    except Exception as e:
        health_status["checks"]["database"] = {
            "status": "error",
            "message": f"Database error: {str(e)}"
        }
        health_status["status"] = "degraded"
    
    # --- Wawacity test ---
    wawacity_start = time.time()
    try:
        response = await http_client.get(WAWACITY_URL, timeout=5)
        wawacity_time = round((time.time() - wawacity_start) * 1000)
        
        if response.status_code == 200:
            health_status["checks"]["wawacity"] = {
                "status": "ok",
                "message": "Wawacity accessible",
                "response_time_ms": wawacity_time
            }
        else:
            health_status["checks"]["wawacity"] = {
                "status": "error",
                "message": f"Wawacity HTTP {response.status_code}",
                "response_time_ms": wawacity_time
            }
            health_status["status"] = "degraded"
            
    except Exception as e:
        wawacity_time = round((time.time() - wawacity_start) * 1000)
        health_status["checks"]["wawacity"] = {
            "status": "error",
            "message": f"Wawacity unreachable: {str(e)}",
            "response_time_ms": wawacity_time
        }
        health_status["status"] = "unhealthy"
    
    # --- Proxy test ---
    if PROXY_URL:
        try:
            test_response = await http_client.get("https://httpbin.org/ip", timeout=5)
            if test_response.status_code == 200:
                health_status["checks"]["proxy"] = {
                    "status": "ok",
                    "message": "Proxy functional"
                }
            else:
                health_status["checks"]["proxy"] = {
                    "status": "error",
                    "message": "Proxy not responding"
                }
                health_status["status"] = "degraded"
        except Exception as e:
            health_status["checks"]["proxy"] = {
                "status": "error",
                "message": f"Proxy error: {str(e)}"
            }
            health_status["status"] = "degraded"
    else:
        health_status["checks"]["proxy"] = {
            "status": "disabled",
            "message": "No proxy configured"
        }
    
    # --- Final response ---
    total_time = round((time.time() - start_time) * 1000)
    health_status["total_response_time_ms"] = total_time
    
    return health_status

# --- Password configuration route ---
@router.get("/password-config", 
           summary="Configuration mot de passe", 
           description="Retourne si un mot de passe est requis pour la configuration")
async def get_password_config():
    return JSONResponse(content={
        "password_required": bool(ADDON_PASSWORD.strip())
    })

# --- Password verification route ---
@router.post("/verify-password", 
            summary="Vérification mot de passe", 
            description="Vérifie si le mot de passe fourni est valide")
async def verify_password(password: str = Query(..., description="Mot de passe à vérifier")):
    if not ADDON_PASSWORD.strip():
        return JSONResponse(content={"valid": True})
    
    valid_passwords = [pwd.strip() for pwd in ADDON_PASSWORD.split(",") if pwd.strip()]
    is_valid = password in valid_passwords
    
    return JSONResponse(content={"valid": is_valid})