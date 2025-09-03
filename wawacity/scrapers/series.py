import asyncio
from typing import List, Dict, Optional
from re import findall, search as re_search
from wawacity.scrapers.base import BaseScraper
from wawacity.core.config import WAWACITY_URL
from wawacity.utils.http_client import http_client
from wawacity.utils.helpers import extract_filename_from_link, format_url, quote_url_param
from wawacity.utils.logger import logger
from selectolax.parser import HTMLParser

class SeriesScraper(BaseScraper):
    
    # --- Main search entry point ---
    async def search(self, title: str, year: Optional[str] = None) -> List[Dict]:
        try:
            # --- Search for series ---
            search_result = await self._search_series(title, year)
            if not search_result:
                return []
            
            # --- Extract all episodes ---
            all_episodes = await self._extract_all_episodes(search_result)
            
            # --- Sort by season then episode ---
            all_episodes.sort(key=lambda x: (
                int(x.get("season", "0")),
                int(x.get("episode", "0")),
                self.quality_sort_key(x)
            ))
            
            return all_episodes
            
        except Exception as e:
            logger.error(f"Series search failed for '{title}': {e}")
            return []
    
    # --- Initial series search ---
    async def _search_series(self, title: str, year: Optional[str] = None) -> Optional[Dict]:
        encoded_title = quote_url_param(str(title)[:31])
        search_url = f"{WAWACITY_URL}/?p=series&search={encoded_title}"
        if year:
            search_url += f"&year={str(year)}"
        
        logger.log("SCRAPER", f"Searching: {search_url}")
        
        try:
            # --- Step 1: Find series link ---
            response = await http_client.get(search_url)
            if response.status_code != 200:
                logger.error(f"Search failed: {response.status_code}")
                return None
            
            parser = HTMLParser(response.text)
            search_nodes = parser.css('a[href^="?p=serie&id="]')
            
            if not search_nodes:
                logger.error(f"No series links found for '{title}'")
                return None
            
            first_link = search_nodes[0].attributes.get("href", "")
            
            # --- Step 2: Get series title from page ---
            series_url = f"{WAWACITY_URL}/{first_link}"
            response2 = await http_client.get(series_url)
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
            logger.error(f"Failed to search series: {e}")
            return None
    
    # --- Extract all episodes from series ---
    async def _extract_all_episodes(self, search_result: Dict) -> List[Dict]:
        all_results = []
        series_link = search_result["link"]
        series_url = f"{WAWACITY_URL}/{series_link}"
        
        try:
            all_series_pages = []
            
            # --- Extract quality/language from first page ---
            page_title = search_result.get("text", "")
            parts = [item for item in page_title.split("|") if item]
            if len(parts) >= 2:
                first_quality_label = parts[1].translate(str.maketrans({'[': '', ']': ''}))
                try:
                    first_items = findall(r"([\w\- ]+)(?!\()", first_quality_label)
                    first_quality = first_items[0].split(" - ")[0] if first_items else first_quality_label.strip()
                    first_language = first_items[0].split(" - ")[1] if len(first_items) > 0 and " - " in first_items[0] else "N/A"
                except (IndexError, ValueError, AttributeError):
                    first_quality = first_quality_label.strip()
                    first_language = "N/A"
            else:
                first_quality = "N/A"
                first_language = "N/A"
                
            all_series_pages.append({
                "quality": first_quality,
                "language": first_language,
                "page_path": series_link
            })
            
            # --- Get other available pages/qualities ---
            response = await http_client.get(series_url)
            if response.status_code == 200:
                parser = HTMLParser(response.text)
                
                # --- Other seasons ---
                other_seasons = parser.css('ul.wa-post-list-ofLinks a[href^="?p=serie&id="]')
                for season_node in other_seasons:
                    season_link = season_node.attributes.get("href", "")
                    if season_link and "saison" in season_link.lower():
                        season_title = season_node.text(strip=True)
                        if "(" in season_title and ")" in season_title:
                            quality_part = season_title.split("(")[-1].replace(")", "")
                        else:
                            quality_part = "N/A"
                        
                        all_series_pages.append({
                            "quality": quality_part,
                            "language": "N/A",
                            "page_path": season_link
                        })
                
                # --- Other qualities/languages ---
                other_qualities = parser.css('ul.wa-post-list-ofLinks a[href^="?p=serie&id="]:has(button)')
                for quality_node in other_qualities:
                    quality_link = quality_node.attributes.get("href", "")
                    if quality_link and "saison" not in quality_link.lower():
                        button_node = quality_node.css_first('button')
                        if button_node:
                            button_text = button_node.text(strip=True)
                            quality_parts = button_text.replace("<i>", "").replace("</i>", "").strip()
                        else:
                            quality_parts = "N/A"
                        
                        all_series_pages.append({
                            "quality": quality_parts,
                            "language": quality_parts,
                            "page_path": quality_link
                        })
            
            # --- Process each page in parallel ---
            page_tasks = []
            for series_page in all_series_pages:
                page_tasks.append(
                    self._extract_episodes_from_page(series_page)
                )
            
            page_results = await asyncio.gather(*page_tasks, return_exceptions=True)
            
            # --- Merge all results ---
            for result in page_results:
                if isinstance(result, list):
                    all_results.extend(result)
            
        except Exception as e:
            logger.error(f"Failed to extract all episodes: {e}")
        
        return all_results
    
    # --- Extract episodes from single page ---
    async def _extract_episodes_from_page(self, series_page: Dict) -> List[Dict]:
        page_results = []
        page_path = series_page.get("page_path", "")
        default_quality = series_page.get("quality", "N/A")
        default_language = series_page.get("language", "N/A")
        
        if not page_path:
            return page_results
        
        series_page_url = f"{WAWACITY_URL}/{page_path}"
        
        try:
            response = await http_client.get(series_page_url)
            if response.status_code != 200:
                return page_results
            
            parser = HTMLParser(response.text)
            
            # --- Get all rows from DDLLinks table ---
            link_rows = parser.css('#DDLLinks tr')
            if not link_rows:
                logger.log("SCRAPER", f"No download links for page: {page_path}")
                return page_results
            
            current_episode = None
            current_season = "1"
            current_page_language = default_language
            current_page_quality = default_quality
            
            for row in link_rows:
                # --- Check if episode title row ---
                row_class = str(row.attributes.get("class", ""))
                if "episode-title" in row_class:
                    episode_text = row.text(strip=True)
                    
                    if "Épisode" in episode_text:
                        # --- Extract episode number ---
                        episode_match = re_search(r"Épisode (\d+)", episode_text)
                        current_episode = episode_match.group(1) if episode_match else "1"
                        
                        # --- Extract season if present ---
                        season_match = re_search(r"Saison (\d+)", episode_text)
                        if season_match:
                            current_season = season_match.group(1)
                        
                        # --- Extract language and quality from episode title ---
                        known_languages = ["VF", "VOSTFR", "MULTI"]
                        
                        episode_language = "N/A"
                        episode_quality = "N/A"
                        
                        for lang in known_languages:
                            lang_pattern = rf"- {lang}([^-]*?)(?:- |en téléchargement|$)"
                            lang_match = re_search(lang_pattern, episode_text)
                            if lang_match:
                                episode_language = lang
                                quality_part = lang_match.group(1).strip()
                                if quality_part:
                                    episode_quality = quality_part
                                else:
                                    episode_quality = ""
                                break
                        
                        # --- Update current variables ---
                        if episode_language != "N/A":
                            current_page_language = episode_language
                            current_page_quality = episode_quality
                
                # --- Check if download link row ---
                elif current_episode is not None:
                    link_node = row.css_first('a[href*="dl-protect."].link')
                    if link_node:
                        # --- Extract link information ---
                        hoster_cell = row.css_first('td[width="120px"].text-center')
                        hoster_name = hoster_cell.text().strip() if hoster_cell else ""
                        
                        # --- Filter supported hosters ---
                        if hoster_name.lower() not in ["1fichier", "turbobit", "rapidgator"]:
                            continue
                        
                        size_td = row.css_first('td[width="80px"].text-center')
                        file_size = size_td.text().strip() if size_td else "?"
                        
                        url = self.extract_link_from_node(link_node)
                        if not url:
                            continue
                        
                        url = format_url(url, WAWACITY_URL)
                        
                        # --- Extract filename ---
                        link_text = link_node.text(strip=True) if link_node else ""
                        decoded_fn = extract_filename_from_link(url, link_text)
                        
                        # --- Validation ---
                        if not current_season or not current_episode or not decoded_fn.strip():
                            logger.error(f"Invalid metadata: S{current_season}E{current_episode}, file: {decoded_fn}")
                            continue
                        
                        page_results.append({
                            "season": current_season,
                            "episode": current_episode,
                            "label": f"S{current_season.zfill(2)}E{current_episode.zfill(2)} - {current_page_quality} - {current_page_language} ({hoster_name.title()})",
                            "language": current_page_language,
                            "quality": current_page_quality,
                            "hoster": hoster_name.title(),
                            "size": file_size,
                            "dl_protect": url,
                            "display_name": decoded_fn
                        })
        
        except Exception as e:
            logger.error(f"Failed to extract episodes from page: {e}")
        
        return page_results

# --- Global instance ---
series_scraper = SeriesScraper()