# -*- coding: utf-8 -*-
from cps.services.worker import CalibreTask
from cps import helper, ub, db, config, logger, app

log = logger.create()


class TaskSendUnsyncedToKindle(CalibreTask):
    def __init__(self, message, user_id):
        super(TaskSendUnsyncedToKindle, self).__init__(message)
        self.user_id = user_id

    @property
    def name(self):
        return "Send Books missing from Kindle"

    @property
    def is_cancellable(self):
        return True

    def run(self, worker_thread):
        sent_count = 0
        skipped_count = 0
        failed_count = 0
        skipped_examples = []

        try:
            with app.app_context():
                from scripts.cwa_db import CWA_DB
                from cps.db import Books

                cwa_db = CWA_DB()
                confirmed_ids = cwa_db.kindle_sync_get_all_confirmed(self.user_id) or set()

                calibre_db_instance = db.CalibreDB(expire_on_commit=False, init=True)
                user = ub.session.query(ub.User).filter(ub.User.id == self.user_id).first()
                if not user:
                    self._handleError(f"User {self.user_id} not found")
                    return

                if not user.kindle_mail:
                    self._handleError(f"User {user.name} has no eReader email configured")
                    return

                all_books = calibre_db_instance.session.query(Books).all()
                unsynced_books = [book for book in all_books if book.id not in confirmed_ids]
                total_books = len(unsynced_books)

                if total_books == 0:
                    self.statmsg = "No books missing from Kindle were found to send."
                    self._handleSuccess()
                    return

                for index, book in enumerate(unsynced_books):
                    if getattr(worker_thread, 'stop_execution', False):
                        self._handleError("Task cancelled")
                        return

                    self.progress = index / total_books

                    email_share_list = helper.check_send_to_ereader(book)
                    if not email_share_list:
                        skipped_count += 1
                        skip_reason = "No email-compatible format under current mail size/conversion settings"
                        cwa_db.kindle_sync_update(self.user_id, book.id, status='error', error_message=skip_reason, reset_retry=False)
                        if len(skipped_examples) < 5:
                            skipped_examples.append(f"{book.title}: {skip_reason}")
                        continue

                    book_format = email_share_list[0]['format']
                    convert_flag = email_share_list[0]['convert']

                    try:
                        with app.test_request_context('/'):
                            result = helper.send_mail(
                                book_id=book.id,
                                book_format=book_format,
                                convert=convert_flag,
                                ereader_mail=user.kindle_mail,
                                calibrepath=config.get_book_path(),
                                user_id=user.name,
                                subject=user.kindle_mail_subject
                            )
                    except Exception as send_exc:
                        result = str(send_exc)
                        log.error(f"Send failed for book {book.id} ('{book.title}'): {send_exc}")

                    if result is None:
                        ub.update_download(book.id, int(user.id))
                        cwa_db.kindle_sync_update(self.user_id, book.id, status='pending', error_message=None, reset_retry=True)
                        sent_count += 1
                    else:
                        cwa_db.kindle_sync_update(self.user_id, book.id, status='error', error_message=str(result), reset_retry=False)
                        failed_count += 1

                self.progress = 1.0
                self.statmsg = f"Queued {sent_count} books missing from Kindle for send (skipped: {skipped_count}, failed: {failed_count})."
                if skipped_examples:
                    self.statmsg += " Skipped examples: " + " | ".join(skipped_examples)
                self._handleSuccess()

        except Exception as e:
            log.error(f"TaskSendUnsyncedToKindle failed: {e}")
            self._handleError(str(e))
        finally:
            try:
                if 'calibre_db_instance' in locals():
                    session = getattr(calibre_db_instance, "session", None)
                    if session:
                        session.close()
            except Exception:
                pass
