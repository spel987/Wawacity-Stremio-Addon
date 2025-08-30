from argparse import ArgumentParser
from sys import exit, stderr
from re import sub, findall, search
from typing import Optional
from requests import Session
from selectolax.parser import HTMLParser, Node
from unicodedata import normalize
from json import dumps
from urllib.parse import quote_plus, urlparse, parse_qs, unquote
from base64 import b64decode

from os import environ

WAWACITY_URL = environ.get("WAWACITY_URL", "https://wawacity.diy")

requests_session = Session()

class UnsuccessfulSearch(Exception):
    """Unsuccessful search on the source."""
    pass

def extract_element_from_page(page_link: str, css_selector: str):
    resp = requests_session.get(page_link, timeout=15)
    if resp.ok:
        nodes = HTMLParser(resp.text).css(css_selector)
        if nodes:
            return nodes

def extract_link_from_node(node: Node):
    link = None
    attributes = node.attributes
    if "href" in attributes.keys():
        link = node.attributes["href"]
    else:
        for value in attributes.values():
            if search(r"^(/|https?:)\w", value):
                link = value
                break
    if link:
        return link
    else:
        raise UnsuccessfulSearch

def extract_link_from_page(page_link: str, css_selector: str):
    link_node = extract_element_from_page(page_link, css_selector)[0]
    return extract_link_from_node(link_node)

def filter_nodes(nodes: list, pattern: str):
    filtered = []
    for node in nodes:
        if isinstance(node, Node):
            if search(pattern, node.text()):
                filtered.append(node)
        else:
            raise UnsuccessfulSearch
    if filtered:
        return filtered
    else:
        raise UnsuccessfulSearch

def normalize_string(string: str):
    return normalize('NFKD', str(string)).encode('ascii', 'ignore').decode('ascii')

def remove_unwanted_characters(string: str):
    return sub("\s+", " ", string.translate(str.maketrans({'-': ' ', ':': '', '–': ' ', '—': ' ', '−': ' '})))

def compare_titles(title_1: str, title_2: str):
    return normalize_string(title_1.casefold()) in normalize_string(title_2.casefold())

def quality_sort_key(item: dict):
    """Sort key according to custom quality precedence:
    - 4K (REMUX > WEB-DL > LIGHT)
    - 1080 (BLURAY > WEB-DL > HDLIGHT)
    - 720 (BLURAY > WEB-DL > HDLIGHT)
    - RIP (WEBRIP > HDRIP)
    - Others at the end
    """
    q = str(item.get("quality", "")).upper()

    def is_4k(qs: str) -> bool:
        return "2160" in qs or "4K" in qs

    def type_rank_4k(qs: str) -> int:
        if "REMUX" in qs:
            return 0
        if "WEB-DL" in qs or "WEBDL" in qs or "WEB DL" in qs:
            return 1
        if "HDLIGHT" in qs or "LIGHT" in qs:
            return 2
        return 98

    def type_rank_hd(qs: str) -> int:
        if "BLURAY" in qs or "BLU-RAY" in qs or "BLU RAY" in qs:
            return 0
        if "WEB-DL" in qs or "WEBDL" in qs or "WEB DL" in qs:
            return 1
        if "HDLIGHT" in qs or "LIGHT" in qs:
            return 2
        return 98

    def is_rip(qs: str) -> bool:
        return "WEBRIP" in qs or "HDRIP" in qs or "HD-RIP" in qs or ("RIP" in qs)

    if is_4k(q):
        group = 0
        t = type_rank_4k(q)
    elif "1080" in q:
        group = 1
        t = type_rank_hd(q)
    elif "720" in q:
        group = 2
        t = type_rank_hd(q)
    elif is_rip(q):
        group = 3
        if "WEBRIP" in q:
            t = 0
        elif "HDRIP" in q or "HD-RIP" in q:
            t = 1
        else:
            t = 98
    else:
        group = 4
        t = 99

    return (group, t)

def search_movie(title: str, year: Optional[str] = None) -> list[dict]:
    print(f"[SEARCH] Search: {title} ({year})", file=stderr)

    encoded_title = quote_plus(str(title)[:31])
    search_url = f"{WAWACITY_URL}/?p=films&search={encoded_title}"
    if year:
        search_url += f"&year={str(year)}"

    try:
        search_page_link = extract_link_from_page(search_url, r'a[href^="?p=film&id="]')

        page_title_node = extract_element_from_page(f"{WAWACITY_URL}/{search_page_link}", r'div.wa-sub-block-title:has(i.flag)')[0]
        page_title = page_title_node.text(strip=True, separator="|")
        parts = [item for item in page_title.split("|") if item]
        if len(parts) < 2:
            raise UnsuccessfulSearch
        first_quality_label = parts[1].translate(str.maketrans({'[': '', ']': ''}))
        movie_title = parts[0]

        cleaned_searched = remove_unwanted_characters(title)
        cleaned_found = remove_unwanted_characters(movie_title)
        if not compare_titles(cleaned_searched, cleaned_found):
            print(f"[SEARCH][WARN] Title different TMDB/Wawacity -> TMDB: '{cleaned_searched}' | Wawacity: '{cleaned_found}'", file=stderr)

        qualities_data: list[dict] = []

        try:
            first_items = findall(r"([\w\- ]+)(?!\()", first_quality_label)
            first_quality = first_items[0].split(" - ")[0]
            first_language = first_items[0].split(" - ")[1]
        except Exception:
            first_quality = first_quality_label.strip()
            first_language = "N/A"
        qualities_data.append({
            "quality": first_quality,
            "language": first_language,
            "page_path": f"{search_page_link}"
        })

        available_qualities = extract_element_from_page(
            f"{WAWACITY_URL}/{search_page_link}", r'a[href^="?p=film&id="]:has(button)'
        )

        if available_qualities:
            for node in available_qualities:
                label_raw = str(node.text().strip())
                items = findall(r"([\w\- ]+)(?!\()", label_raw)
                quality_txt = items[0].strip() if items else label_raw.strip()
                if len(items) >= 3:
                    language_txt = f"{items[1].strip()} ({items[2].strip()})"
                elif len(items) >= 2:
                    language_txt = items[1].strip()
                else:
                    language_txt = "N/A"

                page_link = node.attributes.get("href")
                qualities_data.append({
                    "quality": quality_txt,
                    "language": language_txt,
                    "page_path": page_link
                })

        results: list[dict] = []

        for item in qualities_data:
            page_path = item.get("page_path")
            quality_txt = item.get("quality", "?")
            language_txt = item.get("language", "N/A")
            movie_page_url = f"{WAWACITY_URL}/{page_path}"
            try:
                link_row_nodes = extract_element_from_page(movie_page_url, '#DDLLinks tr.link-row:nth-child(n+2)')
                if not link_row_nodes:
                    print(f"[SEARCH][INFO] No link rows for quality '{quality_txt} ({language_txt})'", file=stderr)
                    continue

                try:
                    filtered_rows = filter_nodes(link_row_nodes, r"Lien .*")
                except Exception:
                    print(f"[SEARCH][INFO] No matching rows for quality '{quality_txt} ({language_txt})'", file=stderr)
                    continue

                for row in filtered_rows:
                    try:
                        hoster_cell = row.css_first('td[width="120px"].text-center')
                        hoster_name = hoster_cell.text().strip() if hoster_cell else ""
                    except Exception:
                        continue

                    if hoster_name.lower() != "1fichier":
                        continue

                    size_td = row.css_first('td[width="80px"].text-center')
                    file_size = size_td.text().strip() if size_td else "?"

                    link_node = row.css_first('a[href*="dl-protect."].link')
                    if not link_node:
                        continue
                    url = extract_link_from_node(link_node)
                    if not url.startswith("http"):
                        url = f"{WAWACITY_URL}{url}" if url.startswith('/') else url

                    parsed_dl_protect = urlparse(url)
                    query_params = parse_qs(parsed_dl_protect.query)
                    fn_encoded = unquote(query_params.get('fn', [None])[0])
                    decoded_fn = b64decode(fn_encoded).decode('utf-8')

                    results.append({
                        "label": f"{quality_txt} - {language_txt}",
                        "language": language_txt,
                        "quality": quality_txt,
                        "size": file_size,
                        "dl_protect": url,
                        "original_name": decoded_fn
                    })
            except Exception as e:
                print(f"[SEARCH][INFO] Skipping quality '{quality_txt} ({language_txt})' due to error: {e}", file=stderr)
                continue

        results.sort(key=quality_sort_key)
        print(f"[SEARCH] {len(results)} result(s) 1fichier.", file=stderr)
        return results

    except Exception as e:
        print(f"[SEARCH][ERROR] {e}", file=stderr)
        return []

def normalize_title(title: str) -> str:
    title = title.lower()

    title = sub(r'[-–—−]', ' ', title)
    title = sub(r'[^\w\s]', ' ', title)
    title = sub(r'\s+', ' ', title)
    title = title.strip()
    return title

def fuzzy_match(search_title: str, db_title: str, threshold: float = 0.8) -> bool:
    search_words = set(search_title.split())
    db_words = set(db_title.split())
    
    if not search_words:
        return False
    
    common_words = search_words.intersection(db_words)
    ratio = len(common_words) / len(search_words)
    
    return ratio >= threshold

def main():
    parser = ArgumentParser(description="Search for films on Wawacity")
    parser.add_argument("--title", required=True, help="Title of the film")
    parser.add_argument("--year", help="Year of release")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    
    args = parser.parse_args()
    
    if args.debug:
        normalized = normalize_title(args.title)
        print(f"Original title: '{args.title}'", file=stderr)
        print(f"Normalized title: '{normalized}'", file=stderr)
        return
    
    results = search_movie(args.title, args.year)
    
    if results:
        print(dumps({"results": results}, ensure_ascii=False))
        exit(0)
    else:
        print(dumps({"results": []}, ensure_ascii=False))
        exit(1)

if __name__ == "__main__":
    main()
