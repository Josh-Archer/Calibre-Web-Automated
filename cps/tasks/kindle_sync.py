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

    def name(self):
        return "Kindle Library Sync"

    def is_cancellable(self):
        return True

    def run(self, worker_thread):
        try:
            from scripts.cwa_db import CWA_DB
            from scripts.kindle_sync import sync_kindle_book
            
            cwa_db = CWA_DB()
            settings = cwa_db.cwa_settings
            
            if not settings.get('amazon_sync_enabled'):
                self._handleSuccess() # Skip if disabled
                return

            cookies = settings.get('amazon_session_cookies', '')
            if not cookies:
                self._handleError("Amazon session cookies are missing in settings.")
                return

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
            status, asin, error = sync_kindle_book(cookies, book.title, book.authors[0].name if book.authors else None)
            
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
