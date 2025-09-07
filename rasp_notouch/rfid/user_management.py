import logging
from django.shortcuts import render
from django.shortcuts import render
from rasp import settings
from rfid import rfid_reader
from rfid.exceptions import CustomException
from rfid.utils import handle_exception
from .models import User_v3, Weight_v3
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger('rasp')
logger.setLevel(logging.INFO)

# 사용자 확인 함수 (ORM 사용)
def check_user(uid):
    try:
        # UID를 기반으로 사용자 검색
        user = User_v3.objects.get(uid=uid)
        logger.info(f"사용자 확인 성공: {user.name}, UID: {uid}")
        return user
    except ObjectDoesNotExist:
        # 사용자를 찾지 못한 경우 예외 처리
        logger.error(f"사용자를 찾을 수 없음: UID {uid}")
        raise CustomException("사용자를 찾을 수 없습니다.", status_code=404)
    except Exception as e:
        # 기타 예외 처리
        logger.error(f"사용자 확인 중 예기치 못한 오류: {str(e)}")
        raise CustomException("서버에서 오류가 발생했습니다.", status_code=500)
    
@handle_exception
def add_user(request):
    name = request.POST.get('name')
    company = request.POST.get('company')
    admin_pw = request.POST.get('admin_pw')
    uid = request.POST.get('uid')
    depart = request.POST.get('department')
    try:
        logger.info(f"사용자 추가 시도: 이름: {name}, 회사: {company}, UID: {uid}")
        
        if admin_pw != settings.ADMIN_PASSWD:
            logger.warning(f"관리자 비밀번호 실패: {admin_pw}")
            raise CustomException("관리자 비밀번호가 잘못되었습니다.", status_code=403)

        if User_v3.objects.filter(uid=uid).exists():
            logger.warning(f"중복된 UID 존재: {uid}")
            raise CustomException("이미 등록된 사용자입니다.", status_code=409)

        asgn_cd = get_asgn_cd(company)
        if asgn_cd == "UNKNOWN":
            raise CustomException("등록되지 않은 업체입니다.", status_code=401)

        # Weight_v3 객체 생성 또는 가져오기
        weight_instance, created = Weight_v3.objects.get_or_create(asgn_cd=asgn_cd, company=company, defaults={'weight': 0.0})
        if created:
            logger.info(f"새로운 회사 무게 정보 생성: {company}")

        # User_v3 객체 생성
        User_v3.objects.create(uid=uid, name=name, asgn_cd=weight_instance, company=company, depart=depart)

        logger.info(f"사용자 추가 성공: 이름: {name}, UID: {uid}")
        return render(request, 'index.html', {'success_addUser': True})

    except Exception as e:
        logger.error(f"사용자 추가 오류: {str(e)}")
        raise CustomException(f"사용자 추가 중 오류 발생: {str(e)}", status_code=500)

    
# 회사코드 생성
# 선행도장부 : 금양기업, 은성기업, 태양인더스트리, 한솔선박
# 도장부     : 미주이엔지, 부림기업, 세왕기업, 안진테크, 찬승, 일영기업, 해강이엔지
# 기장부     : 번영이엔지, 석영
@handle_exception
def get_asgn_cd(company_name):
    company_mapping = {
        
        # 환경보건부
        "환경보건부": 0000,

        # 선행도장부
        "금양기업": 8414,
        "은성기업": 8419,
        "태양인더스트리": 8463,
        "한솔선박": 8417,

        # 도장부
        "미주이엔지": 8466,
        "부림기업": 8460,
        "세왕기업": 8458,
        "안진테크": 8468,
        "찬승": 8469,
        "일영기업": 8459,
        "해강이엔지": 8467,

        # 기장부
        "번영이엔지": 8462,
        "석영": 8645,

    }    
    return company_mapping.get(company_name, "UNKNOWN")
