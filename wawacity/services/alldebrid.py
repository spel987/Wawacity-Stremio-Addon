from typing import Optional
from asyncio import sleep
from wawacity.utils.http_client import http_client
from wawacity.core.config import ALLDEBRID_API_URL, ALLDEBRID_MAX_RETRIES, RETRY_DELAY_SECONDS
from wawacity.utils.logger import logger

class AllDebridService:
    
    # --- Link conversion ---
    async def convert_link(self, dl_protect_link: str, apikey: str) -> Optional[str]:
        if not apikey:
            logger.error("No AllDebrid API key provided")
            return None
        
        logger.log("ALLDEBRID", f"Converting: {dl_protect_link}")
        
        for attempt in range(ALLDEBRID_MAX_RETRIES):
            try:
                # --- Step 1: Resolve redirector ---
                response1 = await http_client.get(
                    f"{ALLDEBRID_API_URL}/link/redirector",
                    params={"agent": "Wawacity", "apikey": apikey, "link": dl_protect_link}
                )
                
                if response1.status_code != 200:
                    logger.error(f"Redirector failed: {response1.status_code} (attempt {attempt + 1}/{ALLDEBRID_MAX_RETRIES}, retry in {RETRY_DELAY_SECONDS}s)")
                    await sleep(RETRY_DELAY_SECONDS)
                    continue
                
                data1 = response1.json()
                if data1.get("status") != "success":
                    error = data1.get("error", {})
                    if error.get("code") == "LINK_HOST_NOT_SUPPORTED":
                        logger.error(f"Redirector error: {error.get('code', 'UNKNOWN')} - {error.get('message', 'Unknown')}")
                        return None
                    elif error.get("code") == "LINK_HOST_UNAVAILABLE":
                        logger.error(f"Redirector error: {error.get('code', 'UNKNOWN')} - {error.get('message', 'Unknown')}")
                        return None
                    elif error.get("code") == "LINK_DOWN":
                        logger.error(f"Redirector error: {error.get('code', 'UNKNOWN')} - {error.get('message', 'Unknown')}")
                        return "LINK_DOWN"
                    
                    logger.error(f"Redirector error: {error.get('code', 'UNKNOWN')} - {error.get('message', 'Unknown')} (attempt {attempt + 1}/{ALLDEBRID_MAX_RETRIES}, retry in {RETRY_DELAY_SECONDS}s)")
                    await sleep(RETRY_DELAY_SECONDS)
                    continue
                
                redirected_links = data1.get("data", {}).get("links", [])
                if not redirected_links:
                    logger.error(f"No redirected links (attempt {attempt + 1}/{ALLDEBRID_MAX_RETRIES}, retry in {RETRY_DELAY_SECONDS}s)")
                    await sleep(RETRY_DELAY_SECONDS)
                    continue
                
                # --- Step 2: Unlock first link ---
                first_link = redirected_links[0]
                response2 = await http_client.get(
                    f"{ALLDEBRID_API_URL}/link/unlock",
                    params={"agent": "Wawacity", "apikey": apikey, "link": first_link}
                )
                
                if response2.status_code != 200:
                    logger.error(f"Unlock failed: {response2.status_code} (attempt {attempt + 1}/{ALLDEBRID_MAX_RETRIES}, retry in {RETRY_DELAY_SECONDS}s)")
                    await sleep(RETRY_DELAY_SECONDS)
                    continue
                
                data2 = response2.json()
                if data2.get("status") != "success":
                    error = data2.get("error", {})
                    
                    if error.get("code") == "LINK_DOWN":
                        logger.error(f"Unlock error: {error.get('code', 'UNKNOWN')} - {error.get('message', 'Unknown')}")
                        return "LINK_DOWN"
                    
                    logger.error(f"Unlock error: {error.get('code', 'UNKNOWN')} - {error.get('message', 'Unknown')} (attempt {attempt + 1}/{ALLDEBRID_MAX_RETRIES}, retry in {RETRY_DELAY_SECONDS}s)")
                    await sleep(RETRY_DELAY_SECONDS)
                    continue
                
                direct_link = data2.get("data", {}).get("link")
                if direct_link:
                    logger.log("ALLDEBRID", "Link converted successfully")
                    return direct_link
                
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {e} (attempt {attempt + 1}/{ALLDEBRID_MAX_RETRIES}, retry in {RETRY_DELAY_SECONDS}s)")
                if attempt < ALLDEBRID_MAX_RETRIES - 1:
                    await sleep(RETRY_DELAY_SECONDS)
        
        logger.error(f"Failed after {ALLDEBRID_MAX_RETRIES} attempts")
        return None

# --- Global instance ---
alldebrid_service = AllDebridService()