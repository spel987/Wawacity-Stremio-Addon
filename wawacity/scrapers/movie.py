import asyncio
from typing import List, Dict, Optional
from re import findall
from wawacity.scrapers.base import BaseScraper
from wawacity.core.config import WAWACITY_URL
from wawacity.utils.http_client import http_client
from wawacity.utils.helpers import format_url, quote_url_param
from wawacity.utils.logger import logger
from selectolax.parser import HTMLParser

class MovieScraper(BaseScraper):
    
    # --- Main search entry point ---
    async def search(self, title: str, year: Optional[str] = None) -> List[Dict]:
        try:
            # --- Search for movie ---
            search_result = await self._search_movie(title, year)
            if not search_result:
                return []
            
            # --- Extract available qualities ---
            qualities_data = await self._extract_qualities(search_result)
            
            # --- Extract links for each quality in parallel ---
            tasks = [self._extract_links_for_quality(quality) for quality in qualities_data]
            results_lists = await asyncio.gather(*tasks, return_exceptions=True)
            
            # --- Merge all results ---
            all_results = []
            for result in results_lists:
                if isinstance(result, list):
                    all_results.extend(result)
                elif not isinstance(result, Exception):
                    logger.error(f"Unexpected result type: {type(result)}")
            
            # --- Sort by quality ---
            all_results.sort(key=self.quality_sort_key)
            
            return all_results
            
        except Exception as e:
            logger.error(f"Movie search failed for '{title}': {e}")
            return []
    
    # --- Initial movie search ---
    async def _search_movie(self, title: str, year: Optional[str] = None) -> Optional[Dict]:
        encoded_title = quote_url_param(str(title)[:31])
        search_url = f"{WAWACITY_URL}/?p=films&search={encoded_title}"
        if year:
            search_url += f"&year={str(year)}"
        
        logger.log("SCRAPER", f"Searching: {search_url}")
        
        try:
            # --- Step 1: Find movie link ---
            response = await http_client.get(search_url)
            if response.status_code != 200:
                logger.error(f"Search failed: {response.status_code}")
                return None
            
            parser = HTMLParser(response.text)
            search_nodes = parser.css('a[href^="?p=film&id="]')
            
            if not search_nodes:
                logger.error(f"No movie links found for '{title}'")
                return None
            
            first_link = search_nodes[0].attributes.get("href", "")
            
            # --- Step 2: Get movie title from page ---
            movie_url = f"{WAWACITY_URL}/{first_link}"
            response2 = await http_client.get(movie_url)
            if response2.status_code != 200:
                return None
            
            parser2 = HTMLParser(response2.text)
            title_nodes = parser2.css('div.wa-sub-block-title:has(i.flag)')
            
            if title_nodes:
                page_title = title_nodes[0].text(strip=True, separator="|")
                if not page_title.strip():
                    logger.error(f"Empty title found for {title}")
                    return None
                return {
                    "link": first_link,
                    "text": page_title
                }
            else:
                logger.error(f"No title found for {title}")
                return {
                    "link": first_link,
                    "text": f"{title} [{year}]" if year else title
                }
            
        except Exception as e:
            logger.error(f"Failed to search movie: {e}")
            return None
    
    # --- Extract available qualities ---
    async def _extract_qualities(self, search_result: Dict) -> List[Dict]:
        qualities_data = []
        page_link = search_result["link"]
        node_text = search_result["text"]
        
        # --- Extract first quality from text ---
        parts = node_text.split("]")
        if len(parts) >= 2:
            first_quality_label = parts[1].translate(str.maketrans({'[': '', ']': ''}))
            
            try:
                items = findall(r"([\w\- ]+)(?!\()", first_quality_label)
                quality = items[0].split(" - ")[0] if items else first_quality_label.strip()
                language = items[0].split(" - ")[1] if len(items) > 0 and " - " in items[0] else "N/A"
            except (IndexError, ValueError, AttributeError):
                quality = first_quality_label.strip()
                language = "N/A"
            
            qualities_data.append({
                "quality": quality,
                "language": language,
                "page_path": page_link
            })
        
        # --- Get other available qualities ---
        movie_url = f"{WAWACITY_URL}/{page_link}"
        
        try:
            response = await http_client.get(movie_url)
            if response.status_code == 200:
                parser = HTMLParser(response.text)
                quality_nodes = parser.css('a[href^="?p=film&id="]:has(button)')
                
                for node in quality_nodes:
                    label_raw = node.text().strip()
                    items = findall(r"([\w\- ]+)(?!\()", label_raw)
                    
                    quality_txt = items[0].strip() if items else label_raw.strip()
                    
                    if len(items) >= 3:
                        language_txt = f"{items[1].strip()} ({items[2].strip()})"
                    elif len(items) >= 2:
                        language_txt = items[1].strip()
                    else:
                        language_txt = "N/A"
                    
                    qualities_data.append({
                        "quality": quality_txt,
                        "language": language_txt,
                        "page_path": node.attributes.get("href", "")
                    })
        except Exception as e:
            logger.error(f"Failed to extract qualities: {e}")
        
        return qualities_data
    
    # --- Extract links for specific quality ---
    async def _extract_links_for_quality(self, quality_data: Dict) -> List[Dict]:
        results = []
        page_path = quality_data.get("page_path", "")
        quality_txt = quality_data.get("quality", "?")
        language_txt = quality_data.get("language", "N/A")
        
        if not page_path:
            return results
        
        movie_page_url = f"{WAWACITY_URL}/{page_path}"
        
        try:
            response = await http_client.get(movie_page_url)
            if response.status_code != 200:
                return results
            
            parser = HTMLParser(response.text)
            link_rows = parser.css('#DDLLinks tr.link-row:nth-child(n+2)')
            
            if not link_rows:
                logger.log("SCRAPER", f"No links for quality '{quality_txt} ({language_txt})'")
                return results
            
            # --- Filter rows with "Lien" ---
            filtered_rows = self.filter_nodes(link_rows, r"Lien .*")
            if not filtered_rows:
                return results
            
            all_links = []
            primary_metadata = None
            
            # --- Extract links ---
            for row in filtered_rows:
                hoster_cell = row.css_first('td[width="120px"].text-center')
                hoster_name = hoster_cell.text().strip() if hoster_cell else ""
                
                # --- Filter supported hosters ---
                if hoster_name.lower() not in ["1fichier", "turbobit", "rapidgator"]:
                    continue
                
                size_td = row.css_first('td[width="80px"].text-center')
                file_size = size_td.text().strip() if size_td else "?"
                
                link_node = row.css_first('a[href*="dl-protect."].link')
                if not link_node:
                    continue
                
                url = self.extract_link_from_node(link_node)
                if not url:
                    continue
                
                url = format_url(url, WAWACITY_URL)
                
                # --- Extract filename ---
                link_text = link_node.text(strip=True) if link_node else ""
                original_filename = link_text.split(":")[-1].strip() if ":" in link_text else ""
                
                all_links.append({
                    "hoster": hoster_name.lower(),
                    "url": url
                })
                
                # --- Save primary metadata ---
                if not primary_metadata:
                    primary_metadata = {
                        "size": file_size,
                        "display_name": original_filename
                    }
            
            # --- Create results for each link ---
            for link_data in all_links:
                hoster_name = link_data["hoster"].title()
                results.append({
                    "label": f"{quality_txt} - {language_txt} ({hoster_name})",
                    "language": language_txt,
                    "quality": quality_txt,
                    "hoster": hoster_name,
                    "size": primary_metadata.get("size", "?") if primary_metadata else "?",
                    "dl_protect": link_data["url"],
                    "display_name": primary_metadata.get("display_name", "?") if primary_metadata else "?"
                })
            
        except Exception as e:
            logger.error(f"Failed to extract links for quality '{quality_txt}': {e}")
        
        return results

# --- Global instance ---
movie_scraper = MovieScraper()