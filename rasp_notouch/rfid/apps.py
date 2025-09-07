from django.apps import AppConfig
import os
import logging

logger = logging.getLogger('rasp')

class RfidConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rfid'

    def ready(self):
        # 개발 서버 reload 중복 실행 방지
        if os.environ.get('RUN_MAIN') != 'true':
            return

        from apscheduler.schedulers.background import BackgroundScheduler
        from django_apscheduler.jobstores import DjangoJobStore
        from rfid.session_tasks import check_timeout_sessions

        scheduler = BackgroundScheduler()
        scheduler.add_jobstore(DjangoJobStore(), "default")
        scheduler.add_job(check_timeout_sessions, 'interval', minutes=1, id='check_sessions', replace_existing=True)
        scheduler.start()

        logger.info("APScheduler 시작됨 (세션 타임아웃 자동 정리)")
