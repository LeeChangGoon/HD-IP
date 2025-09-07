import logging
from datetime import timedelta
from django.utils import timezone
from django.contrib.sessions.models import Session
from rfid.hardware import get_lock

logger = logging.getLogger('rasp')

def check_timeout_sessions():
    now = timezone.now()
    expired_time = now - timedelta(minutes=30)

    for session in Session.objects.all():
        data = session.get_decoded()
        uid = data.get('uid')
        start_time = data.get('start_time')

        if uid and start_time:
            try:
                start_dt = timezone.datetime.fromisoformat(start_time)
                if start_dt < expired_time:
                    # 30분 초과 → 문 닫기 & 세션 정리
                    lock = get_lock()
                    lock.on()

                    data.pop('uid', None)
                    data.pop('cur_weight', None)
                    data.pop('start_time', None)
                    session.session_data = Session.objects.encode(data)
                    session.save()

                    logger.warning(f"[자동정리] UID={uid} 30분 경과 → 문 닫음 & 세션 초기화")
            except Exception as e:
                logger.error(f"세션 처리 중 오류: {e}")
