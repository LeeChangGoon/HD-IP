# 공통 예외 처리 함수
from functools import wraps
import logging
from django.shortcuts import render

from rfid.exceptions import CustomException

logger = logging.getLogger('rasp')
logger.info("로깅 시작")

def handle_exception(func):
    """View 함수의 공통 예외 처리를 위한 데코레이터"""
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        try:
            return func(request, *args, **kwargs)
        except CustomException as e:
            if e.status_code == 555:
                uid = kwargs.get('uid')
                name = kwargs.get('name')
                company = kwargs.get('company')
                weight_info = kwargs.get('weight_info', {'message': '잠금 해제에 이용한 카드를 대주세요.'})

                return render(request, 'err_lock.html', {
                    'uid': uid,
                    'name': name,
                    'company': company,
                    'message': weight_info['message'],
                })
            elif e.status_code == 556:
                uid = kwargs.get('uid')
                name = kwargs.get('name')
                company = kwargs.get('company')
                weight_info = kwargs.get('weight_info', {'message': '카드를 다시 대주세요.'})

                return render(request, 'err_lock.html', {
                    'uid': uid,
                    'name': name,
                    'company': company,
                    'message': weight_info['message'],
                })
            #무게 추출 실패 --> 484
            elif e.status_code == 484:
                uid = kwargs.get('uid')
                name = kwargs.get('name')
                company = kwargs.get('company')
                weight_info = kwargs.get('weight_info', {'message': '카드를 다시 대주세요.'})

                return render(request, 'err_lock.html', {
                    'uid': uid,
                    'name': name,
                    'company': company,
                    'message': weight_info['message'],
                })
            logger.warning(f"CustomException 발생: {e}")
            return render(request, 'error.html', {
                'message': str(e),
                'status_code': e.status_code,
            }, status=e.status_code)
        except Exception as e:
            logger.error(f"예기치 못한 오류: {e}", exc_info=True)
            return render(request, 'error.html', {
                'message': "내부 서버 오류가 발생했습니다.",
                'status_code': 500,
            }, status=500)
    return wrapper