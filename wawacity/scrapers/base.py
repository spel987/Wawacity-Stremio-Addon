from typing import List, Dict, Optional, Any
from selectolax.parser import HTMLParser, Node
from re import search
from wawacity.utils.http_client import http_client

class BaseScraper:
    
    # --- Link extraction ---
    @staticmethod
    def extract_link_from_node(node: Node) -> Optional[str]:
        link = None
        attributes = node.attributes
        
        if "href" in attributes:
            link = attributes["href"]
        else:
            for value in attributes.values():
                if search(r"^(/|https?:)\w", value):
                    link = value
                    break
        return link
    
    # --- Node filtering ---
    @staticmethod
    def filter_nodes(nodes: List[Node], pattern: str) -> List[Node]:
        filtered = []
        for node in nodes:
            if isinstance(node, Node) and search(pattern, node.text()):
                filtered.append(node)
        return filtered
    
    # --- Quality sorting ---
    @staticmethod
    def quality_sort_key(item: Dict[str, Any]) -> tuple:
        q = str(item.get("quality", "")).upper()
        
        # --- 4K detection ---
        is_4k = "2160" in q or "4K" in q or "UHD" in q
        
        # --- 1080p detection ---
        is_1080 = "1080" in q or q == "HD"
        
        # --- 720p detection ---
        is_720 = "720" in q
        
        # --- Release type ranking ---
        if "REMUX" in q:
            release_type = 0
        elif "BLURAY" in q or "BLU-RAY" in q:
            release_type = 1
        elif "WEB-DL" in q or "WEBDL" in q:
            release_type = 2
        elif "HDLIGHT" in q or "LIGHT" in q:
            release_type = 3
        elif "WEBRIP" in q:
            release_type = 4
        elif "HDRIP" in q:
            release_type = 5
        else:
            release_type = 99
        
        # --- Final sorting priority ---
        if is_4k:
            return (0, release_type)
        elif is_1080:
            return (1, release_type)
        elif is_720:
            return (2, release_type)
        else:
            return (99, release_type)