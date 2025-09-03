from typing import Optional, Dict
from wawacity.utils.http_client import http_client
from wawacity.core.config import TMDB_API_URL
from wawacity.utils.logger import logger

class TMDBService:
    
    BASE_URL = TMDB_API_URL
    
    # --- Metadata fetching ---
    async def get_metadata(self, imdb_id: str, tmdb_key: str) -> Optional[Dict]:
        url = f"{self.BASE_URL}/find/{imdb_id}?external_source=imdb_id"
        headers = {
            "Authorization": f"Bearer {tmdb_key}",
            "Content-Type": "application/json",
        }
        
        try:
            response = await http_client.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # --- Check for movies ---
                if data.get("movie_results"):
                    movie = data["movie_results"][0]
                    title = movie["original_title"] if movie.get("original_language") == "fr" else movie["title"]
                    year = movie.get("release_date", "").split("-")[0]
                    return {"title": title, "year": year, "type": "movie"}
                
                # --- Check for series ---
                elif data.get("tv_results"):
                    tv_show = data["tv_results"][0]
                    title = tv_show["original_name"] if tv_show.get("original_language") == "fr" else tv_show["name"]
                    year = tv_show.get("first_air_date", "").split("-")[0]
                    return {"title": title, "year": year, "type": "series"}
            
            return None
            
        except Exception as e:
            logger.error(f"TMDB metadata fetch failed: {e}")
            return None

# --- Global instance ---
tmdb_service = TMDBService()