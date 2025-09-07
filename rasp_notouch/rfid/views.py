import json
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.shortcuts import render, redirect
from django.urls import reverse
import gpiozero
from mfrc522 import SimpleMFRC522
from rasp import settings
from rfid.exceptions import CustomException
from gpiozero import DigitalOutputDevice
import spidev
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 50000  # SPI 속도를 50kHz로 낮춤

# Create your views here.


#잠금장치 ---> on이 열림 / off가 잠김
# lock = DigitalOutputDevice(21, active_high=False)

# 메인 페이지
def index(request):
    # DigitalOutputDevice(16).off()
    return render(request, 'index.html')

# #폐기 페이지
# def disposal(request, state, message, uid, user, company):

#     return render(request, 'disposal.html', {# disposal.html에 사용자 정보와 폐기량 정보 전달
#                             'message': message,
#                             'user': user,
#                             'uid': uid
#                         })   

#처음 댔던 카드를 대도록 하는 함수
def disposal_err_return(request):
    message = "올바른 카드를 인식해주세요."
    name = request.GET.get('name')
    company = request.GET.get('company')
    uid = request.GET.get('uid')
    user = User_Control.check_user(uid)  # UID로 사용자 확인

    return render(request, 'disposal.html', {
                'message': message,
                'user': user,
                'uid': uid,
                'company': company
    })

#사용자 관리 클래스
class User_Control:
    # RFID 태그 읽기 및 사용자 확인
    def read_tag(request):
        try:
            reader = SimpleMFRC522(reset_pin=16)  # RFID리더기 객체 생성, 실제 연결된 gpio핀 번호로 리셋핀 설정
            uid, data = reader.read() # RFID 태그 읽기
            user = User_Control.check_user(uid)  # UID로 사용자 확인
            if user:
                # 확인된 사용자의 이름을 포함한 메시지
                message = f"사용자 {user.name}이(가) 확인되었습니다."
                lock.on()
                # return disposal(True, "확인", uid, user, user.company)
                return render(request, 'disposal.html', {# disposal.html에 사용자 정보와 폐기량 정보 전달
                    'message': message,
                    'user': user,
                    'uid': uid
                })
            else:
                # 사용자가 확인되지 않은 경우
                message = f"인가된 사용자가 아닙니다. UID: {id}"
                return render(request, 'error.html', {'message': '해당 사용자가 없습니다.'})
        # except GPIOPinInUse:
        #     return render(request, 'error.html', {'message': "GPIO핀 리소스 정리 필요"})
        except Exception as e:
            # 오류 발생 시 에러 페이지로 이동
            print(e)
            DigitalOutputDevice(16).off()
            return render(request, 'error.html', {'message': f"태깅 중 에러 발생: {e}"})

    # 사용자 추가(태깅으로 uid입력)
    def add_user(request):
        if request.method == 'POST':
            # 사용자가 입력한 이름과 회사 정보 받기
            name = request.POST.get('name')
            company = request.POST.get('company')
            admin_pw = request.POST.get('admin_pw')
            # 관리자 비밀번호 검증
            if admin_pw != settings.ADMIN_PASSWD:
                return render(request, 'error.html', {'message': '잘못된 관리자 비밀번호입니다.'})
            
            if name and company:  # 입력 데이터 유효성 검사
                try:
                    reader = SimpleMFRC522(reset_pin=16)  # RFID리더기 객체 생성, 실제 연결된 gpio핀 번호로 리셋핀 설정
                    # RFID 태그 읽기
                    uid, data = reader.read()

                    # ORM을 사용해 사용자 추가 (uid, name, company 정보 저장)
                    if User.objects.filter(uid=uid).exists():
                        return render(request, 'error.html', {'message': '사용자가 이미 존재합니다.'})
                    else: 
                        User.objects.create(uid=uid, name=name, company=company)
                        # 회사가 중복되지 않으면 초기 무게 데이터 생성
                        if not Weight.objects.filter(company=company).exists():
                            Weight.objects.create(company=company, weight=0)
                    # 저장 후 메인 페이지로 리디렉션
                    return render(request, 'index.html', {'success_addUser': True}) #success: 모달 띄우기 위한 플래그
                # except GPIOPinInUse:
                #     return render(request, 'error.html', {'message': "GPIO핀 리소스 정리 필요"})

                except Exception as e:
                    # 오류 발생 시 에러 페이지로 이동
                    return render(request, 'error.html', {'message': f"Error saving data: {e}"})
            else:
                return render(request, 'error.html', {'message': 'Invalid input data'})
        return render(request, 'add_user.html')
    
    # 사용자 확인 함수 (ORM 사용)
    def check_user(id):
        try:
            user = User.objects.get(uid=id)
            return user
        except User.DoesNotExist:
            return None
        
    #카드 추가 페이지
    def add_card(request):
        return render(request, 'add_user.html')   
     
#폐기량 관리 클래스
class Paint_Control:
    # 무게값 업데이트 함수
    def update_weight(company, name):        
        if company:
            try:
                # 해당 회사의 현재 상태를 가져옴(id | company | weight)
                cur_state = Weight.objects.get(company=company)

                # 로드셀에서 읽어온 무게 (부은 후의 변화된 무게) -> disposal_weight
                disposal_weight = 123  # 모듈에서 실제 값을 읽어오는 코드가 들어갈 예정

                #회사 폐기량
                company_disposal = disposal_weight+cur_state.weight
                # 현재 무게 업데이트
                cur_state.weight = company_disposal
                cur_state.save()

                # Message와 폐기량을 함께 반환
                message = f"{name}님의 폐기량은 {disposal_weight}kg입니다."
                return {'message': message, 'disposal_weight': disposal_weight, 'company_weight': company_disposal}

            except Weight.DoesNotExist:
                return {'error': "무게 정보가 없습니다.", 'status': 404}
            except Exception as e:
                return {'error': f"오류가 발생했습니다: {str(e)}", 'status': 500}
        else:
            return {'error': "회사명이 입력되지 않았습니다.", 'status': 400}

    # 폐기 후 결과 화면 보여주기
    def result(request):
        if request.method == 'GET':
            name = request.GET.get('name')
            company = request.GET.get('company')
            uid = request.GET.get('uid')
           
            tagging_result = Paint_Control.lockTag(name, company)
            # if tagging_result['Timeout']:
            #     return render(request, 'result.html', {'Timeout': True}) #success: 모달 띄우기 위한 플래그


            if tagging_result['result']:  # 태그 확인 성공
                lock.off()
                weight_info = Paint_Control.update_weight(company, name)
                if 'error' in weight_info:
                    # 오류 메시지와 상태 코드를 반환
                    return render(request, 'error.html', {'message': weight_info})
                else:
                    # 성공적으로 폐기량을 계산한 경우
                    return render(request, 'result.html', {
                        'name': name,
                        'company': company,
                        'message': weight_info['message'],
                        'Weight': weight_info['disposal_weight'],
                        'Company_Weight': weight_info['company_weight'],
                    })
            else:
                return render(request, 'err_lock.html', {
                'message': '초기에 읽은 카드와 맞지 않습니다.',
                'company': company,
                'name': name,
                'uid': uid
                })

    # 처음에 댔던 태그랑 맞는지 비교
    def lockTag(name, company):
        reader = SimpleMFRC522(reset_pin=16)  # RFID 리더기 초기화
        try:
            uid, data = reader.read()
            if uid == None:
                return {'Timeout': True}
            disposal_User = User_Control.check_user(uid)
            if disposal_User.name == name and disposal_User.company == company:
                return {'result': True, 'uid': uid}
            else:
                return {'result': False, 'uid': uid}
        except Exception as e:
            return {'error': f"오류가 발생했습니다: {str(e)}", 'status': 500}

# MQTT 테이블 정보 전송 (테스트용)
def publish_weight(request):
    # 데이터 가져오기
    data = Weight.objects.all().values()  # 데이터 딕셔너리로 가져옴
    print(data)
    data_list = list(data)  # 쿼리셋을 리스트로 변환
    message = json.dumps(data_list, ensure_ascii=False)  # JSON 문자열로 변환, 두번째 옵션은 한글 처리.

    # MQTT 메시지 발행
    publish.single("test_local/rp165", message, hostname="10.150.8.165")
    print("데이터 발행:", message)

    return render(request, 'index.html')