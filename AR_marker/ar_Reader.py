import os
import re
import glob
import cv2
import pandas as pd
import numpy as np
from openpyxl.drawing.image import Image as XLImage  # 이미지 삽입
from pathlib import Path

# ===== 0) 사용자 설정 =====
image_dir = r"Z:\03_혁신운영과\26) IoT과제 발굴심의 협의체\3.IoT 개발 과제\2511_선각1B공장 강재추적_DMIC\10. 영상기반\강재 AR부착사진\case_1"
excel_path = os.path.join(image_dir, "marker_bottom_y.xlsx")
thumb_dir = os.path.join(image_dir, "_excel_thumbs")  # 썸네일 저장 폴더
os.makedirs(thumb_dir, exist_ok=True)

# 엑셀에 넣을 이미지 최대 가로폭(픽셀). 너무 크면 엑셀 용량이 커집니다.
THUMB_MAX_W = 900

# 오버레이 이미지(마커 박스/ID/아래쪽 y 라인) 생성해서 넣기
EMBED_OVERLAY = True

# 처리할 이미지 확장자
EXTS = ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.tif", "*.tiff")


# ===== 1) 유틸 =====
def load_image_any_path(path: str):
    """한글/공백 경로 안전 로드: np.fromfile + cv2.imdecode"""
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)

def save_thumb(img_bgr: np.ndarray, save_path: str, max_w: int = THUMB_MAX_W):
    """썸네일 저장(PNG). 가로 기준으로 축소."""
    h, w = img_bgr.shape[:2]
    if w > max_w:
        ratio = max_w / float(w)
        new_size = (max_w, int(h * ratio))
        img_bgr = cv2.resize(img_bgr, new_size, interpolation=cv2.INTER_AREA)
    # PNG로 저장
    cv2.imencode(".png", img_bgr)[1].tofile(save_path)
    return save_path

def draw_overlay(img_bgr: np.ndarray, corners_list, ids_arr, marker_info):
    """
    corners_list: detectMarkers 결과 corners(list of (1,4,2))
    ids_arr     : detectMarkers 결과 ids(np.ndarray Nx1)
    marker_info : [(max_y, marker_id), ...] (정렬 전/후 무관)
    """
    out = img_bgr.copy()
    # 마커 박스 & ID
    for i, corner in enumerate(corners_list):
        pts = corner[0].astype(int)  # (4,2)
        # 테두리
        cv2.polylines(out, [pts], isClosed=True, color=(0, 200, 0), thickness=3)
        # ID 표기(좌상단 근처)
        mid = pts.mean(axis=0).astype(int)
        top_left = tuple(pts[0])
        txt = f"ID {int(ids_arr[i][0])}"
        cv2.putText(out, txt, (top_left[0], top_left[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 60, 255), 3, cv2.LINE_AA)

    # 아래쪽 y(가장 큰 y) 수평선
    H = out.shape[0]
    W = out.shape[1]
    for max_y, m_id in marker_info:
        y = int(round(max_y))
        cv2.line(out, (0, y), (W-1, y), (255, 180, 0), 2)
        cv2.putText(out, f"max_y({m_id})={y}", (10, max(30, y - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 180, 0), 2, cv2.LINE_AA)
    return out

def clean_sheet_name(name: str) -> str:
    """파일명 -> 엑셀 시트명(금지문자 제거, 31자 제한)"""
    base = os.path.splitext(name)[0]
    base = re.sub(r'[:\\/?*\[\]]', '_', base)
    return base[:31] or "sheet"


# ===== 2) 이미지 수집 =====
image_files = []
for pat in EXTS:
    image_files += glob.glob(os.path.join(image_dir, pat))
if not image_files:
    raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_dir}")

# 파일명(베이스) -> 원본 경로
file_map = {os.path.basename(p): p for p in image_files}


# ===== 3) ArUco 준비 (버전 호환) =====
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
try:
    parameters = cv2.aruco.DetectorParameters()
except AttributeError:
    parameters = cv2.aruco.DetectorParameters_create()

try:
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
    use_new_api = True
except AttributeError:
    detector = None
    use_new_api = False


# ===== 4) 처리 =====
rows = []        # 엑셀 표 데이터
thumb_for_file = {}  # 각 파일별로 삽입할 썸네일 경로

for f in image_files:
    img = load_image_any_path(f)
    fname = os.path.basename(f)

    print(f"\n=== {fname} ===")
    if img is None:
        print("[경고] 이미지 로드 실패")
        rows.append([fname, None, None, None])
        # 그래도 이미지 썸네일 생성 시도(원본이 없으니 생략)
        continue

    # 마커 검출
    if use_new_api:
        corners, ids, _ = detector.detectMarkers(img)
    else:
        corners, ids, _ = cv2.aruco.detectMarkers(img, aruco_dict, parameters=parameters)

    if ids is None or len(ids) == 0:
        print("마커 없음")
        rows.append([fname, None, None, None])
        # 이미지 썸네일(원본 그대로) 저장
        thumb_path = os.path.join(thumb_dir, Path(fname).stem + "_thumb.png")
        save_thumb(img, thumb_path, THUMB_MAX_W)
        thumb_for_file[fname] = thumb_path
        continue

    # 각 마커의 가장 아래쪽 y 계산
    marker_info = []
    for i, corner in enumerate(corners):
        ys = corner[0][:, 1]
        max_y = float(ys.max())  # 아래로 갈수록 y 큼
        marker_id = int(ids[i][0])
        marker_info.append((max_y, marker_id))

    # 아래쪽(큰 y) -> 위쪽(작은 y) 정렬
    marker_info.sort(reverse=True, key=lambda x: x[0])

    # 터미널 출력 + 결과 누적
    for idx, (max_y, marker_id) in enumerate(marker_info):
        print(f"{idx:02d}\tID={marker_id}\tmax_y={max_y:.2f}")
        rows.append([fname, f"{idx:02d}", marker_id, max_y])

    # 엑셀 삽입용 이미지(오버레이 or 원본) 썸네일 저장
    if EMBED_OVERLAY:
        img_overlay = draw_overlay(img, corners, ids, marker_info)
        thumb_path = os.path.join(thumb_dir, Path(fname).stem + "_overlay_thumb.png")
        save_thumb(img_overlay, thumb_path, THUMB_MAX_W)
    else:
        thumb_path = os.path.join(thumb_dir, Path(fname).stem + "_thumb.png")
        save_thumb(img, thumb_path, THUMB_MAX_W)
    thumb_for_file[fname] = thumb_path


# ===== 5) DataFrame & 엑셀 저장(통합 + 파일별 시트 + 이미지 삽입) =====
df = pd.DataFrame(rows, columns=["파일명", "순번", "마커값", "아래쪽 Y좌표"])

# openpyxl 필요: pip install openpyxl pillow
with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
    # (1) 통합 시트
    df.to_excel(writer, sheet_name="all_results", index=False)
    ws_all = writer.sheets["all_results"]
    ws_all.freeze_panes = "A2"
    ws_all.column_dimensions["A"].width = 40
    ws_all.column_dimensions["B"].width = 8
    ws_all.column_dimensions["C"].width = 10
    ws_all.column_dimensions["D"].width = 14

    # (2) 파일별 시트 + 이미지 삽입
    used = {"all_results"}
    for fname, g in df.groupby("파일명", sort=False):
        sheet = clean_sheet_name(fname)
        base = sheet
        i = 2
        while sheet in used:
            sheet = clean_sheet_name(f"{base}_{i}")
            i += 1
        used.add(sheet)

        g.to_excel(writer, sheet_name=sheet, index=False)
        ws = writer.sheets[sheet]
        ws.freeze_panes = "A2"

        # 표 가독성
        ws.column_dimensions["A"].width = 40  # 파일명
        ws.column_dimensions["B"].width = 8   # 순번
        ws.column_dimensions["C"].width = 10  # 마커값
        ws.column_dimensions["D"].width = 14  # 아래쪽 Y좌표

        # 이미지 삽입(썸네일)
        img_path = thumb_for_file.get(fname)
        if img_path and os.path.exists(img_path):
            try:
                xlimg = XLImage(img_path)
                # G2에 앵커(표 오른쪽에 이미지가 보이게)
                ws.add_image(xlimg, "F2")
            except Exception as e:
                print(f"[이미지 삽입 실패] {fname}: {e}")

print(f"\n엑셀 저장 완료: {excel_path}")
print(f"썸네일/오버레이 파일 폴더: {thumb_dir}")
