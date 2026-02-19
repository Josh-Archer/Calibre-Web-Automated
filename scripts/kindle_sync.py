# -*- coding: utf-8 -*-
import requests
import json
import time
from datetime import datetime, timezone

def sync_kindle_book(cookies_str, title, author=None, csrf_token=None, logger=None):
    """
    Attempts to find a book in Amazon's MYCD library using session cookies.
    Returns (status, asin, error_message)
    """
    def log_info(msg):
        if logger:
            logger.info(msg)
        else:
            print(msg)

    def log_error(msg):
        if logger:
            logger.error(msg)
        else:
            print(msg)

    if not cookies_str:
        return 'error', None, 'Missing Amazon session cookies'

    # Convert cookie string to dict
    cookies = {}
    for item in cookies_str.split(';'):
        if '=' in item:
            name, value = item.strip().split('=', 1)
            cookies[name] = value

    url = "https://www.amazon.com/hz/mycd/ajax"
    
    # Standard payload for listing books
    payload = {
        "param": {
            "listEntities": {
                "sortOrder": "DESCENDING",
                "sortIndex": "DATE",
                "startIndex": 0,
                "maxResults": 50,
                "itemToken": None,
                "entityType": "Books"
            }
        }
    }
    
    if csrf_token:
        payload["csrfToken"] = csrf_token

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest"
    }

    try:
        # Amazon requires some CSRF tokens usually, but often session cookies are enough for AJAX if origin/referer is correct
        # We might need to fetch the page once to get tokens if this fails
        response = requests.post(url, data={"data": json.dumps(payload)}, cookies=cookies, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return 'error', None, f"HTTP {response.status_code}: {response.text[:100]}"

        data = response.json()
        
        # Structure varies, but usually: data['Value']['items']
        items = data.get('Value', {}).get('items', [])
        
        if not items:
            log_error(f"[kindle-sync] No items returned from Amazon. Check cookies/session. Response snippet: {response.text[:200]}")
            return 'not_found', None, 'No items returned from Amazon'

        # Match logic: simple title/author check
        normalized_title = title.lower().strip()
        normalized_author = author.lower().strip() if author else ""
        
        log_info(f"[kindle-sync] Searching for '{title}' (normalized: '{normalized_title}')")
        log_info(f"[kindle-sync] First 5 items from Amazon:")
        for i, item in enumerate(items[:5]):
            log_info(f"  {i+1}: {item.get('title')} by {item.get('authors')} (ASIN: {item.get('asin')})")

        for item in items:
            item_title = item.get('title', '').lower().strip()
            item_authors = item.get('authors', '').lower().strip()
            asin = item.get('asin')
            
            # Match title exactly or as substring
            if normalized_title in item_title or item_title in normalized_title:
                # If author provided, check it too
                if not normalized_author or (normalized_author in item_authors or item_authors in normalized_author):
                    return 'confirmed', asin, None

        return 'not_found', None, f"Book '{title}' not found in the first 50 items on Amazon"

    except Exception as e:
        return 'error', None, str(e)

if __name__ == "__main__":
    # Test script if needed
    pass
