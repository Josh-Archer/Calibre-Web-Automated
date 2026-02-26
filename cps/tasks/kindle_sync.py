# -*- coding: utf-8 -*-
import time
from datetime import datetime, timezone, timedelta
from ..services.worker import CalibreTask, STAT_FINISH_SUCCESS, STAT_FAIL
from .. import logger, calibre_db

log = logger.create()

class TaskKindleSync(CalibreTask):
    def __init__(self, message, book_id, user_id, max_retries=10):
        super(TaskKindleSync, self).__init__(message)
        self.book_id = book_id
        self.user_id = user_id
        self.max_retries = max_retries

    @property
    def name(self):
        return "Kindle Library Sync"

    @property
    def is_cancellable(self):
        return True

    def run(self, worker_thread):
        try:
            from scripts.cwa_db import CWA_DB
            from scripts.kindle_sync import sync_kindle_book, fetch_all_amazon_items
            
            cwa_db = CWA_DB()
            settings = cwa_db.cwa_settings
            
            if not settings.get('amazon_sync_enabled'):
                self._handleSuccess() # Skip if disabled
                return

            cookies = settings.get('amazon_session_cookies', '')
            csrf_token = settings.get('amazon_csrf_token', '')
            if not cookies:
                self._handleError("Amazon session cookies are missing in settings.")
                return

            ebook_items, pdoc_items, updated_cookies, fetch_err = fetch_all_amazon_items(cookies, logger=log)
            if fetch_err:
                self._handleError(f"Failed to fetch Amazon library: {fetch_err}")
                return

            if updated_cookies and updated_cookies != cookies:
                try:
                    cwa_db.update_cwa_settings({'amazon_session_cookies': updated_cookies})
                    cookies = updated_cookies
                except Exception as e:
                    log.debug(f"Failed to persist updated Amazon cookies: {e}")

            book = calibre_db.get_book(self.book_id)
            if not book:
                self._handleError(f"Book ID {self.book_id} not found in library.")
                return

            # Check if already confirmed
            current_status = cwa_db.kindle_sync_get_status(self.user_id, self.book_id)
            if current_status and current_status['status'] == 'confirmed':
                self._handleSuccess()
                return

            # Perform the sync
            status, asin, error = sync_kindle_book(
                cookies,
                book.title,
                book.authors[0].name if book.authors else None,
                csrf_token=csrf_token,
                logger=log,
                pre_fetched_items=(ebook_items, pdoc_items)
            )
            
            # Update DB
            cwa_db.kindle_sync_update(self.user_id, self.book_id, status=status, asin=asin, error_message=error)
            
            if status == 'confirmed':
                self._handleSuccess()
            elif status == 'not_found':
                # This task instance is done (it was one attempt)
                self._handleSuccess()
            else:
                self._handleError(error or "Unknown error during sync")

        except Exception as e:
            log.error(f"Kindle Sync Task failed: {e}")
            self._handleError(str(e))
