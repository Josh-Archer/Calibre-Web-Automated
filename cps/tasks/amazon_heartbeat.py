# -*- coding: utf-8 -*-
from ..services.worker import CalibreTask, STAT_FINISH_SUCCESS, STAT_FAIL
from .. import logger
import time
from datetime import datetime, timezone

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
                fail_count = int(settings.get('amazon_heartbeat_fail_count', 0) or 0) + 1
                cwa_db.update_cwa_settings({
                    'amazon_heartbeat_fail_count': fail_count,
                    'amazon_heartbeat_last_error': 'Missing Amazon session cookies'
                })
                self._handleSuccess()
                return

            self.statmsg = "Refreshing Amazon Session..."
            
            updated_cookies, err = amazon_session_heartbeat(cookies, logger=log)
            if err:
                log.error(f"[amazon-heartbeat] Failed: {err}")
                fail_count = int(settings.get('amazon_heartbeat_fail_count', 0) or 0) + 1
                cwa_db.update_cwa_settings({
                    'amazon_heartbeat_fail_count': fail_count,
                    'amazon_heartbeat_last_error': str(err)[:1000]
                })
                self._handleError(f"Heartbeat failed: {err}")
                return
                
            if updated_cookies and updated_cookies != cookies:
                log.info("[amazon-heartbeat] Session cookies updated, persisting to DB.")
                cwa_db.update_cwa_settings({'amazon_session_cookies': updated_cookies})

            cwa_db.update_cwa_settings({
                'amazon_heartbeat_fail_count': 0,
                'amazon_heartbeat_last_error': '',
                'amazon_heartbeat_last_success_utc': datetime.now(timezone.utc).isoformat()
            })
            
            self.statmsg = "Amazon Session refreshed successfully."
            self._handleSuccess()

        except Exception as e:
            log.error(f"Amazon Heartbeat Task failed: {e}")
            try:
                from scripts.cwa_db import CWA_DB
                cwa_db = CWA_DB()
                settings = cwa_db.cwa_settings
                fail_count = int(settings.get('amazon_heartbeat_fail_count', 0) or 0) + 1
                cwa_db.update_cwa_settings({
                    'amazon_heartbeat_fail_count': fail_count,
                    'amazon_heartbeat_last_error': str(e)[:1000]
                })
            except Exception:
                pass
            self._handleError(str(e))
