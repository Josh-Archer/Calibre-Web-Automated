import sys
sys.path.insert(1, 'c:/Code/Calibre-Web-Automated/scripts/')
from cwa_db import CWA_DB

cookies = "session-id=139-3444411-0701718;at-main=Atza|gQDSie1rAwEBAPeHkBVQg53jMC0kVR_kyK1-wHZ0F2RUp7wJ9MXGLGqFpu2oVHq8UN7C2Q0mgSe0rVLf_oDfSOaS3uZ_r9R2NGqu5eUQ8ddRkku5Io6IaaVtXFJ8xo6ixwHNNyKUJCOibmWBE0XKnE6OvAWZ94UhA9kDEk0LR9mOq7JTe8K60emy47FFiPmlcylWb2zrOYKAxStgWZjER834AjSJJVVVbGiLBT6dYwesIiRm6hk45R1nx95TFa-6bwLJVIBUYjIP0_nBLaQ9x2Tg32AlSQX7EEat8OXotkA6cNtFKZIHVnyDi7TRaz3cp_rZdZAoLm9ms9F9uUwCB8uLyyJJtsUKgBPgwwk5nElMciMotg6QXP_GT1T8-kO5;ubid-main=135-3457116-1593011;"

cwa_db = CWA_DB()
cwa_db.update_cwa_settings({
    "amazon_sync_enabled": 1,
    "amazon_session_cookies": cookies
})
print("Successfully updated Amazon cookies in settings.")
