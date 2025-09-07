import time
from mfrc522 import SimpleMFRC522
from rfid.exceptions import CustomException
import spidev
from smartcard.System import readers
from smartcard.util import toHexString

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 100000 #표준이 10kHz


# Create your tests here.
import logging

# 로깅 설정
logger = logging.getLogger('rasp')
logger.info("로깅 시작")

def read_card_uid():
    # return 'DF 79 1A 82'
    # return 'DF 78 1A 82' 추가 테스트용
    flag = True
    while flag:

        try:
            available_readers = readers()
            if not available_readers:
                logger.error("리더기를 찾을 수 없습니다. 연결 상태를 확인하세요.")
                raise CustomException(f"리더기를 찾을 수 없습니다. {str(e)}", status_code=500)

            # print("사용 가능한 리더기:", available_readers)
            reader = available_readers[0] 
            connection = reader.createConnection()
            connection.connect()

            # UID 읽기 명령
            get_uid_command = [0xFF, 0xCA, 0x00, 0x00, 0x00]
            data, sw1, sw2 = connection.transmit(get_uid_command)

            if sw1 == 0x90 and sw2 == 0x00:
                uid = toHexString(data)
                print(f"카드 UID: {uid}")
                flag=False
                return uid
            else:
                print(f"UID 읽기 실패: SW1={sw1}, SW2={sw2}")
                raise CustomException(f"리더기를 찾을 수 없습니다. {str(e)}", status_code=500)


        except Exception as e:
            error_message = str(e)
            if "No smart card inserted" in error_message:
                # print("카드가 삽입되지 않았습니다. 기다리는 중...")
                time.sleep(1)
            else:
                print(f"오류 발생: {e}")
                break