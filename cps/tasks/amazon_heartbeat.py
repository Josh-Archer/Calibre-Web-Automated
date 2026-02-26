# -*- coding: utf-8 -*-
from ..services.worker import CalibreTask, STAT_FINISH_SUCCESS, STAT_FAIL
from .. import logger
import time

log = logger.create()

class TaskAmazonHeartbeat(CalibreTask):
    def __init__(self, message, user_id=1):
        super(TaskAmazonHeartbeat, self).__init__(message)
        self.user_id = user_id

    @property
    def name(self):
        return "Amazon Session Heartbeat"

    @property
    def is_cancellable(self):
        return False

    def run(self, worker_thread):
        try:
            from scripts.cwa_db import CWA_DB
            from scripts.kindle_sync import amazon_session_heartbeat
            
            cwa_db = CWA_DB()
            settings = cwa_db.cwa_settings
            
            cookies = settings.get('amazon_session_cookies', '')
            if not cookies:
                log.info("[amazon-heartbeat] No cookies found in settings, skipping heartbeat.")
                self._handleSuccess()
                return

            self.statmsg = "Refreshing Amazon Session..."
            
            updated_cookies, err = amazon_session_heartbeat(cookies, logger=log)
            if err:
                log.error(f"[amazon-heartbeat] Failed: {err}")
                self._handleError(f"Heartbeat failed: {err}")
                return
                
            if updated_cookies and updated_cookies != cookies:
                log.info("[amazon-heartbeat] Session cookies updated, persisting to DB.")
                cwa_db.update_cwa_settings({'amazon_session_cookies': updated_cookies})
            
            self.statmsg = "Amazon Session refreshed successfully."
            self._handleSuccess()

        except Exception as e:
            log.error(f"Amazon Heartbeat Task failed: {e}")
            self._handleError(str(e))
