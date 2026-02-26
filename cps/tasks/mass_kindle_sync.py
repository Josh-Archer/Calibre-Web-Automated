# -*- coding: utf-8 -*-
from ..services.worker import CalibreTask, STAT_FINISH_SUCCESS, STAT_FAIL
from .. import logger, calibre_db

log = logger.create()

class TaskMassKindleSync(CalibreTask):
    def __init__(self, message, user_id, max_retries=1):
        super(TaskMassKindleSync, self).__init__(message)
        self.user_id = user_id
        self.max_retries = max_retries

    @property
    def name(self):
        return "Mass Kindle Library Sync"

    @property
    def is_cancellable(self):
        return True

    def run(self, worker_thread):
        try:
            from scripts.cwa_db import CWA_DB
            from scripts.kindle_sync import fetch_all_amazon_items, sync_kindle_book
            
            cwa_db = CWA_DB()
            settings = cwa_db.cwa_settings
            
            cookies = settings.get('amazon_session_cookies', '')
            if not cookies:
                self._handleError("Amazon session cookies are missing in settings.")
                return

            self.statmsg = "Fetching Amazon Library..."
            
            ebook_items, pdoc_items, updated_cookies, fetch_err = fetch_all_amazon_items(cookies, logger=log)
            if fetch_err:
                self._handleError(f"Failed to fetch Amazon library: {fetch_err}")
                return
            
            if updated_cookies and updated_cookies != cookies:
                log.info("Amazon session cookies updated during fetch, persisting to DB.")
                cwa_db.update_cwa_settings({'amazon_session_cookies': updated_cookies})
                cookies = updated_cookies # Use fresh cookies for subsequent per-book calls if any
                
            total_fetched = len(ebook_items) + len(pdoc_items)
            log.info(f"Successfully fetched {total_fetched} items from Amazon for mass sync.")
            
            if total_fetched == 0:
                self._handleSuccess()
                return

            self.statmsg = f"Comparing {total_fetched} Amazon items with local library..."

            # Iterate over all books in Calibre DB
            from ..db import Books
            all_books = calibre_db.session.query(Books).all()
            total_books = len(all_books)
            matched_count = 0
            
            for index, book in enumerate(all_books):
                if getattr(worker_thread, 'stop_execution', False):
                    self._handleError("Task cancelled.")
                    return
                    
                self.progress = index / total_books

                
                title = book.title
                author = book.authors[0].name if book.authors else None
                
                status, asin, error = sync_kindle_book(
                    cookies_str=cookies, 
                    title=title, 
                    author=author, 
                    logger=log, 
                    pre_fetched_items=(ebook_items, pdoc_items)
                )
                
                cwa_db.kindle_sync_update(self.user_id, book.id, status=status, asin=asin, error_message=error)
                if status == 'confirmed':
                    matched_count += 1
            
            self.progress = 1.0
            self.statmsg = f"Sync complete. Matched {matched_count} / {total_books} local books."
            self._handleSuccess()

        except Exception as e:
            log.error(f"Mass Kindle Sync Task failed: {e}")
            self._handleError(str(e))
