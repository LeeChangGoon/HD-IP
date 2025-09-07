import json
import logging
import re
import serial
from rfid import user_management
from rfid.exceptions import CustomException
from .models import Weight_v3
import paho.mqtt.client as mqtt


logger = logging.getLogger('rasp')
logger.setLevel(logging.INFO)

from decimal import Decimal

# Decimal 타입을 처리하기 위한 함수 정의
def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)  # 또는 str(obj)로 변환 가능
    raise TypeError(f"Type {type(obj)} not serializable")


# 저울에서 무게 읽어오기
def get_weight_v2():
    # return 0
    PORT = "/dev/serial0"
    BAUDRATE = 9600
    TIMEOUT = 1
    WEIGHT_PATTERN = r"-?\s*\d+\.\d{1,2}\s*kg"  # 음수와 공백 허용

    total_weight = 0
    count = 0

    try:
        ser = serial.Serial(
            port=PORT,
            baudrate=BAUDRATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=TIMEOUT,
            rtscts=False,
            xonxoff=False,
        )
        logger.info("저울과 통신 시작")
        
        for _ in range(3):
            try:
                # 원본 데이터 읽기
                data = ser.readline().decode("ascii", errors="ignore").strip()
                # 제어 문자 제거
                cleaned_data = re.sub(r"[^\x20-\x7E]", "", data)
                # 정규 표현식으로 무게 추출
                match = re.search(WEIGHT_PATTERN, cleaned_data)
                if match:
                    # 공백 제거 후 float로 변환
                    weight_str = match.group().replace('kg', '').replace(' ', '').strip()
                    weight = float(weight_str)
                    # logger.info(f"추출된 무게 값: {weight}")

                    if weight <= 0:
                        weight = 0.0
                    total_weight += weight
                    count += 1
                else:
                    logger.warning("무게 값을 추출할 수 없습니다.")
            except Exception as e:
                logger.warning(f"데이터 처리 중 오류 발생: {e}")

        if count == 0:
            raise CustomException("유효한 데이터가 수신되지 않았습니다.(저울)", status_code=484)

        avg_weight = total_weight / count
        logger.info(f"평균 무게 값: {avg_weight}")
        return avg_weight

    except serial.SerialException as e:
        logger.error(f"시리얼 통신 오류: {e}")
        raise CustomException(f"시리얼 통신 오류: {e}", status_code=404)

    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            logger.info("직렬 포트를 닫았습니다.")


def update_weight(company, name, cur_weight):

    if not company:
        logger.warning("회사명이 입력되지 않았습니다.")
        return {'error': "회사명이 입력되지 않았습니다.", 'status': 400}
    
    asgn_cd = user_management.get_asgn_cd(company)

    try:
        cur_state = Weight_v3.objects.get(asgn_cd = asgn_cd) # 현재 해당 기업 무게

        disposal_weight = get_weight_v2() - cur_weight # 현재 저울에 띄워져있는 무게 - 이전 사이클을 돌았을 때의 무게 --> 무게 변화량

        company_disposal = float(cur_state.weight) + disposal_weight

        if(company_disposal < 0): company_disposal = 0
        
        cur_state.weight = company_disposal
        cur_state.save()

        message = f"{name}님의 폐기량은 {disposal_weight:.2f}kg입니다."
        logger.info(message)
        return {'message': message, 'disposal_weight': disposal_weight, 'company_weight': company_disposal}

    except Weight_v3.DoesNotExist:
        logger.error(f"회사 '{company}' 데이터가 없습니다.")
        raise CustomException("회사 무게 데이터가 존재하지 않습니다.", status_code=404)

    except Exception as e:
        logger.error(f"서버 오류 발생: {e}")
        raise CustomException("서버 오류 발생", status_code=500)

def publish_weight(company, disposal_weight, topic="test/rp165"):  
    """
    payload 예: [ {"ASGN_CD":"HMD", "company":"HD현대미포", "weight":100}, ... ]
    """
    client = mqtt.Client("rp165")
    client.connect("10.150.232.41")
    client.reconnect_delay_set(min_delay=1, max_delay=60)

    try:
        # DB에서 asgn_cd(정수/문자 어떤 타입이 와도 4자리 문자열로 보정)
        rows = list(
            Weight_v3.objects
            .filter(company=company)
            .values("asgn_cd", "company")
        )

        payload = []
        for r in rows:
            asgn = r["asgn_cd"]
            # 정수면 4자리 제로패딩, 문자열이어도 zfill(4)로 통일
            if isinstance(asgn, int):
                asgn_str = f"{asgn:04d}"
            else:
                asgn_str = str(asgn).zfill(4)

            payload.append({
                "asgn_cd": asgn_str,
                "company": r["company"],
                "weight": disposal_weight,  # 숫자 그대로 유지
            })

        # JSON 변환
        message = json.dumps(payload, ensure_ascii=False)  # default=decimal_default 필요시 유지

        # MQTT 발행(QoS 1 권장) 및 전송 완료 대기
        info = client.publish(topic, message, qos=0, retain=False)
        info.wait_for_publish()

        logger.info("MQTT 메시지 발행 완료: %s", message)

    except Exception as e:
        logger.error(f"MQTT 발행 중 오류 발생: {e}")
        raise CustomException("MQTT 발행 오류", status_code=500)
    finally:
        client.disconnect()

# def publish_weight(company, disposal_weight):  # 이상적인 형태는 [ {“ASGN_CD”:”HMD”, “company”:”HD현대미포”, “weight”:100} , … ] 
#     client = mqtt.Client("rp165")
#     client.connect("10.150.8.62")
#     client.reconnect_delay_set(min_delay=1, max_delay=60)

#     try:

#         weight_info = list(Weight_v3.objects.filter(company=company).values("asgn_cd", "company"))
#         # 새로운 데이터 추가
#         for item in weight_info:
#             item["weight"] = disposal_weight  # weight 값 추가

#         # JSON 변환
#         message = json.dumps(weight_info, ensure_ascii=False, default=decimal_default)

#         # MQTT 메시지 발행
#         client.publish("test/rp165", message)
#         logger.info("MQTT 메시지 발행 완료: %s", message)
        
#     except Exception as e:
#         logger.error(f"MQTT 발행 중 오류 발생: {e}")
#         raise CustomException("MQTT 발행 오류", status_code=500)
#     finally:
#         client.disconnect()
