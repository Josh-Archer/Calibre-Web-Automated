# -*- coding: utf-8 -*-
import requests
import json
import re
import time
from datetime import datetime, timezone

KINDLE_HEADER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _parse_cookie_header(cookie_header):
    parsed = {}
    if not cookie_header:
        return parsed
    for part in str(cookie_header).split(';'):
        part = part.strip()
        if not part or '=' not in part:
            continue
        key, value = part.split('=', 1)
        key = key.strip()
        if key:
            parsed[key] = value.strip()
    return parsed


def _merge_cookie_headers(existing_cookie_header, refreshed_cookie_dict):
    merged = _parse_cookie_header(existing_cookie_header)
    for key, value in (refreshed_cookie_dict or {}).items():
        if key:
            merged[str(key)] = str(value)
    return '; '.join([f"{k}={v}" for k, v in merged.items()])

MYCD_AJAX_URL = "https://www.amazon.com/hz/mycd/ajax"


def _fetch_ownership_data(session, csrf_token, content_type, ajax_headers, log_info, log_error):
    """Fetch all books of a given contentType from Amazon OwnershipData."""
    all_items = []
    start_index = 0
    batch_size = 100
    
    while start_index < 5000:  # safety limit to prevent infinite loops
        payload = {
            "param": {
                "OwnershipData": {
                    "sortOrder": "DESCENDING",
                    "sortIndex": "DATE",
                    "startIndex": start_index,
                    "batchSize": batch_size,
                    "contentType": content_type,
                    "itemStatuses": ["ARCHIVED", "AVAILABLE"],
                }
            }
        }
        # Ebooks have originType; personal docs need isExtendedMYK: False
        if content_type == "Ebook":
            payload["param"]["OwnershipData"]["originType"] = ["Purchase"]
        else:
            payload["param"]["OwnershipData"]["isExtendedMYK"] = False

        post_data = {"data": json.dumps(payload)}
        if csrf_token:
            post_data["csrfToken"] = csrf_token

        time.sleep(0.5)
        r = session.post(MYCD_AJAX_URL, data=post_data, headers=ajax_headers, timeout=30)
        
        if not r.ok:
            log_error(f"[kindle-sync] [{content_type}] HTTP Error: {r.status_code}")
            break

        try:
            result = r.json()
        except Exception:
            log_error(f"[kindle-sync] [{content_type}] Failed to parse JSON.")
            break

        top_err = result.get("error") or result.get("Error")
        if top_err:
            log_error(f"[kindle-sync] [{content_type}] API Error: {top_err}")
            break

        ownership = result.get("OwnershipData", {})
        items = ownership.get("items", [])
        total = ownership.get("numberOfItems", 0)
        
        if not items:
            break
            
        all_items.extend(items)
        log_info(f"[kindle-sync] [{content_type}] Fetched {len(items)} items at index {start_index}. Total so far: {len(all_items)}/{total}")
        
        start_index += batch_size
        if isinstance(total, int) and len(all_items) >= total:
            break
            
    return all_items


def fetch_all_amazon_items(cookies_str, logger=None):
    """
    Fetches both purchased Ebooks and personal documents once.
    Returns (ebook_items, pdoc_items, error_message).
    """
    def log_info(msg):
        try:
            with open("/tmp/kindle_sync_debug.log", "a") as f:
                f.write(f"[INFO] {msg}\n")
        except Exception:
            pass
        if logger:
            logger.info(msg)

    def log_error(msg):
        try:
            with open("/tmp/kindle_sync_debug.log", "a") as f:
                f.write(f"[ERROR] {msg}\n")
        except Exception:
            pass
        if logger:
            logger.error(msg)

    if not cookies_str:
        return [], [], None, 'Missing Amazon session cookies'

    session = requests.Session()
    session.headers.update(KINDLE_HEADER)
    session.headers["Cookie"] = cookies_str.strip()

    log_info(f"[kindle-sync] Cookie header length: {len(cookies_str)}")

    csrf_token = None
    log_info("[kindle-sync] Fetching fresh CSRF token from Amazon page")
    try:
        page_resp = session.get("https://www.amazon.com/hz/mycd/myx", timeout=20)
        match = re.search(r'var csrfToken = "([^"]+)"', page_resp.text)
        if match:
            csrf_token = match.group(1)
            log_info(f"[kindle-sync] Auto-fetched CSRF token")
        else:
            log_error("[kindle-sync] Could not find csrfToken in page source")
            log_error(f"[kindle-sync] Page preview: {page_resp.text[:500]}")
    except Exception as e:
        log_error(f"[kindle-sync] Could not fetch page: {e}")

    ajax_headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.amazon.com",
        "Referer": "https://www.amazon.com/hz/mycd/myx",
    }
    if csrf_token:
        ajax_headers["anti-csrftoken-a2z"] = csrf_token

    try:
        live_ebooks = _fetch_ownership_data(session, csrf_token, "Ebook", ajax_headers, log_info, log_error)
        live_pdocs = _fetch_ownership_data(session, csrf_token, "KindlePDoc", ajax_headers, log_info, log_error)
        
        # Merge helper to deduplicate by ASIN
        def _item_key(item):
            asin = str(item.get('asin', item.get('ASIN', '')) or '').strip()
            if asin:
                return f"asin:{asin}"
            content_id = str(item.get('contentId', item.get('ContentId', '')) or '').strip()
            if content_id:
                return f"cid:{content_id}"
            title = item.get('title') or item.get('Title') or item.get('sortableTitle') or ''
            title = str(title).strip().lower()
            authors = item.get('authors') or item.get('author') or item.get('Authors') or item.get('sortableAuthors') or ''
            if isinstance(authors, list):
                authors = ' '.join(str(a) for a in authors if a)
            author = str(authors or '').strip().lower()
            if title or author:
                return f"ta:{title}|{author}"
            return None

        final_ebooks = live_ebooks
        final_pdocs = live_pdocs

        log_info(f"[kindle-sync] Final library state: {len(final_ebooks)} Ebooks, {len(final_pdocs)} PDOCs (live fetch only)")

        # Get updated cookies from session
        updated_cookies = session.cookies.get_dict()
        cookie_string = _merge_cookie_headers(cookies_str, updated_cookies)
        
        return final_ebooks, final_pdocs, cookie_string if cookie_string else cookies_str, None
    except Exception as e:
        log_error(f"[kindle-sync] Exception fetching all items: {e}")
        return [], [], None, str(e)


def amazon_session_heartbeat(cookies_str, logger=None):
    """
    Accesses the Amazon MYX page to keep the session alive.
    Returns (updated_cookies, error_message)
    """
    def log_info(msg):
        if logger: logger.info(msg)
    def log_error(msg):
        if logger: logger.error(msg)

    if not cookies_str:
        return None, 'Missing Amazon session cookies'

    session = requests.Session()
    session.headers.update(KINDLE_HEADER)
    session.headers["Cookie"] = cookies_str.strip()

    try:
        log_info("[amazon-heartbeat] Accessing Amazon MYX page to refresh session...")
        page_resp = session.get("https://www.amazon.com/hz/mycd/myx", timeout=20)
        if page_resp.ok:
            updated_cookies = session.cookies.get_dict()
            cookie_string = _merge_cookie_headers(cookies_str, updated_cookies)
            log_info("[amazon-heartbeat] Session refreshed successfully.")
            return cookie_string if cookie_string else cookies_str, None
        else:
            log_error(f"[amazon-heartbeat] Failed to refresh session: HTTP {page_resp.status_code}")
            return None, f"HTTP {page_resp.status_code}"
    except Exception as e:
        log_error(f"[amazon-heartbeat] Exception during heartbeat: {e}")
        return None, str(e)


def sync_kindle_book(cookies_str, title, author=None, csrf_token=None, logger=None, pre_fetched_items=None):
    """
    Attempts to find a book in Amazon's MYCD library using session cookies.
    Searches both purchased Ebooks AND personal documents (Send-to-Kindle).
    If pre_fetched_items is provided (ebook_items, pdoc_items), it uses them instead of fetching.
    Returns (status, asin, error_message)
    """
    def log_info(msg):
        try:
            with open("/tmp/kindle_sync_debug.log", "a") as f:
                f.write(f"[INFO] {msg}\n")
        except Exception:
            pass
        if logger:
            logger.info(msg)

    def log_error(msg):
        try:
            with open("/tmp/kindle_sync_debug.log", "a") as f:
                f.write(f"[ERROR] {msg}\n")
        except Exception:
            pass
        if logger:
            logger.error(msg)

    if not cookies_str and not pre_fetched_items:
        return 'error', None, 'Missing Amazon session cookies'

    # Match logic helper
    import re
    def clean_text(text):
        if not text:
            return ''
        text_str = str(text).lower()
        text_str = text_str.replace('&', 'and')
        return re.sub(r'[^a-z0-9]', '', text_str)

    def clean_words(text):
        cleaned = clean_text(text)
        if not cleaned:
            return set()
        words = re.findall(r'[a-z0-9]+', str(text).lower().replace('&', 'and'))
        return {w for w in words if len(w) > 2} or ({cleaned} if cleaned else set())
        
    normalized_title = title.lower().strip()
    normalized_author = author.lower().strip() if author else ""
    log_info(f"[kindle-sync] Searching for: '{normalized_title}' by '{normalized_author}'")

    clean_ntitle = clean_text(normalized_title)
    clean_nauthor = clean_text(normalized_author)
    title_words = clean_words(normalized_title)
    author_words = clean_words(normalized_author)

    def find_match(items, content_type_label):
        log_info(f"[kindle-sync] Checking {len(items)} items in {content_type_label} category")
        
        for item in items:
            ititle = item.get('title', item.get('Title', ''))
            iauthors = item.get('authors', item.get('author', item.get('Authors', '')))
            if isinstance(iauthors, list):
                iauthors = ' '.join(str(a) for a in iauthors if a)
            asin = item.get('asin', item.get('ASIN', ''))
            
            # CWA: Support Send-to-Kindle (PDOC) metadata which often leaves 'title' empty 
            # but populates 'sortableTitle' and 'sortableAuthors'.
            if not ititle:
                ititle = item.get('sortableTitle', '')
            if not iauthors:
                iauthors = item.get('sortableAuthors', '')
            
            log_info(f"[DEBUG-SYNC] [{content_type_label}] Checking Amazon title: '{ititle}'")

            clean_ititle = clean_text(ititle)
            clean_iauthor = clean_text(iauthors)
            item_author_words = clean_words(iauthors)

            if not clean_ititle or len(clean_ititle) < 2:
                continue

            # Check title using pure alphanumeric subset
            title_match = False
            if clean_ntitle and ((clean_ntitle in clean_ititle) or (clean_ititle in clean_ntitle)):
                title_match = True
            elif title_words:
                item_title_words = clean_words(ititle)
                overlap = len(title_words & item_title_words)
                # Accept when there is meaningful token overlap for PDOC/library variants
                if overlap >= 2 or (len(title_words) <= 2 and overlap >= 1):
                    title_match = True

            if not title_match:
                continue

            # Check author
            author_match = False
            if not clean_nauthor:
                author_match = True
            elif clean_iauthor and clean_iauthor != 'unknown':
                if (clean_nauthor in clean_iauthor) or (clean_iauthor in clean_nauthor):
                    author_match = True
                elif author_words and len(author_words & item_author_words) >= 2:
                    author_match = True
                elif '@' in str(iauthors):
                    # For Send-to-Kindle, Amazon frequently sets author to the sender email address.
                    author_match = True
            else:
                # For Send-to-Kindle, author metadata is frequently stripped yielding '' or 'unknown'. 
                if len(clean_ntitle) >= 5:
                    author_match = True

            if author_match:
                log_info(f"[kindle-sync] MATCH FOUND in {content_type_label}: '{ititle}' ASIN={asin}")
                return 'confirmed', asin, None
        return None

    try:
        if pre_fetched_items:
            if isinstance(pre_fetched_items, dict):
                ebook_items = pre_fetched_items.get('ebook_items', [])
                pdoc_items = pre_fetched_items.get('pdoc_items', [])
            elif isinstance(pre_fetched_items, (list, tuple)) and len(pre_fetched_items) >= 2:
                ebook_items, pdoc_items = pre_fetched_items[0], pre_fetched_items[1]
            else:
                return 'error', None, 'Invalid pre_fetched_items payload'
        else:
            # 1. Search Ebooks
            ebook_items, pdoc_items, _, fetch_err = fetch_all_amazon_items(cookies_str, logger)
            if fetch_err:
                return 'error', None, fetch_err
        
        res = find_match(ebook_items, "EBOOK")
        if res: return res

        res = find_match(pdoc_items, "PDOC")
        if res: return res

        total = len(ebook_items) + len(pdoc_items)
        log_info(f"[kindle-sync] No match found. Total items checked: {total}")
        
        return 'not_found', None, f"Book '{title}' not found in {total} items on Amazon."

    except Exception as e:
        log_error(f"[kindle-sync] Exception: {e}")
        return 'error', None, str(e)

if __name__ == "__main__":
    pass
