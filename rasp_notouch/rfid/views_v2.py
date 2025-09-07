import logging
from django.http import JsonResponse
from django.shortcuts import render
from rfid import rfid_reader, user_management, weight
from rfid.exceptions import CustomException
from rfid.utils import handle_exception
from gpiozero import DigitalOutputDevice
from rfid.hardware import get_lock
# 로깅 설정
logger = logging.getLogger('rasp')
logger.setLevel(logging.INFO)  # 먼저 로깅 레벨 설정
logger.info("로깅 시작")
# logger.info("현재무게: %.2f", weight.get_weight_v2())



# 메인 --> 폐기
@handle_exception
def check_rfid(request):
    # return JsonResponse({"uid": "04 E3 43 6A 76 13 90"}, status=200) # 이창환_사무실
    # return JsonResponse({"uid": "DF 79 1A 82"}, status=200) # 손채현_환경보건부

    try:
        uid = rfid_reader.read_card_uid()  # RFID 태그 읽기 시도
        if uid:
            return JsonResponse({"uid": uid}, status=200)  # UID 반환
        return JsonResponse({"uid": None}, status=204)  # 태깅 안 됨
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)  # 오류 발생 시

# 폐기 --> 결과
@handle_exception
def check_rfid_disposal(request):
    # return JsonResponse({"tagged": True, "uid": "04 E3 43 6A 76 13 90"}, status=200) # 이창환_사무실
    # return JsonResponse({"tagged": True, "uid": "DF 79 1A 82"}, status=200) # 손채현_환경보건부

    # 폐기 작업 중 RFID 태그 상태를 확인하는 API.
    current_uid = request.GET.get('current_uid')  # 현재 작업 중인 UID
    if not current_uid:
        return JsonResponse({"error": "현재 UID가 없습니다."}, status=400)

    try:
        uid = rfid_reader.read_card_uid()  # RFID 태그 읽기 시도
        if uid:
            return JsonResponse({"tagged": True, "uid": uid}, status=200)  # UID 반환
        return JsonResponse({"tagged": False, "uid": None}, status=200)  # 태깅 안 됨
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)  # 오류 발생 시

    
def set_session(request, key, value):
    # 세션 데이터 설정 함수
    request.session[key] = value


def get_session(request, key):
    # 세션 데이터 가져오기 함수

    return request.session.get(key)


def delete_session(request, key):
    # 세션 데이터 삭제 함수

    if key in request.session:
        del request.session[key]


@handle_exception
def homePage(request):
    lock = get_lock()
    lock.off()  # 문 열기 # 잠금 장치 닫기
    delete_session(request, 'uid')
    delete_session(request, 'current_weight')
    return render(request, 'home.html')

# 잠금장치 해제 후 메인 화면 렌더링
@handle_exception
def index(request):

    lock = get_lock()
    lock.off()  # 문 열기 # 잠금 장치 닫기
    return render(request, 'index.html')

# 카드 추가 페이지 렌더링
@handle_exception
def add_card(request):
    return render(request, 'add_user.html')

@handle_exception
def del_card(request):
    return render(request, 'del_user.html')

# 폐기 중 화면 렌더링
@handle_exception
def disposal(request, uid):
    # RFID 태깅 및 처리 화면
    try:
        if not uid:
            raise CustomException("RFID 태그를 읽을 수 없습니다.", status_code=400)
        # 세션에 UID 저장
        user = user_management.check_user(uid)
        set_session(request, 'uid', uid)
        set_session(request, 'cur_weight', weight.get_weight_v2())
        request.session.set_expiry(32 * 60)

        # logger.info("현재 무게: %.2f", weight.get_weight_v2())

        if not user:
            raise CustomException("사용자를 찾을 수 없습니다.", status_code=404)
        # 처리 성공 시 잠금 장치 해제 
        lock = get_lock()  
        lock.on() # 열기
        message = f"사용자 {user.name}이(가) 확인되었습니다."
        return render(request, 'disposal.html', {'message': message, 'user': user, 'uid': user.uid})

    except CustomException as e:
        logger.warning(f"처리 중 오류 발생: {e}")
        return render(request, 'error.html', {'message': e.message})
    except Exception as e:
        logger.error(f"알 수 없는 오류: {e}")
        return render(request, 'error.html', {'message': "예기치 못한 오류가 발생했습니다."})

# 처리 결과 화면
@handle_exception
def result(request):
    logger.info("Result 호출")

    # 전달된 UID 확인
    uid = request.GET.get('uid')
    if not uid:
        logger.error("UID가 전달되지 않았습니다.")
        raise CustomException("UID가 전달되지 않았습니다.", status_code=400)

    # 세션에 저장된 UID와 비교
    uid_Sess = get_session(request, 'uid')
    if not uid_Sess:
        raise CustomException("세션에 UID가 없습니다.", status_code=400)
    if str(uid) != str(uid_Sess):
        raise CustomException("태그된 UID가 일치하지 않습니다.", status_code=555)

    try:
        user = user_management.check_user(uid)
        name = user.name
        company = user.company

        cur_weight = get_session(request, 'cur_weight')
        
        weight_info = weight.update_weight(company, name, cur_weight)

        # 잠금 장치 닫기
        lock = get_lock()  
        lock.off()
        #데이터 발행
        weight.publish_weight(company, weight_info.get('disposal_weight'))
        return render(request, 'result.html', {
            'name': name,
            'company': company,
            'message': weight_info['message'],
            'Weight': weight_info['disposal_weight'],
            'Company_Weight': weight_info['company_weight'],
        })
    except CustomException as e:
        logger.warning(f"결과 처리 중 오류 발생: {e}")
        return render(request, 'error.html', {'message': e.message})
    finally:
        delete_session(request, 'uid')
        delete_session(request, 'cur_weight')


@handle_exception
def disposal_err(request):
    if request.method != 'GET':
        raise CustomException("잘못된 요청입니다.", status_code=400)
    message = "다시 태깅해주세요."
    uid = request.session.get('uid')
    user = user_management.check_user(uid)

    return render(request, 'disposal.html', {'message': message, 'user': user, 'uid': uid})