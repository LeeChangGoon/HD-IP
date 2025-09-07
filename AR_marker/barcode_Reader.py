import os
import re
import glob
import cv2
import pandas as pd
import numpy as np
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional
from pyzbar.pyzbar import decode, ZBarSymbol
from openpyxl.drawing.image import Image as XLImage

# ===== 설정 (기본값, CLI로 재정의 가능) =====
DEFAULT_IMAGE_DIR = r"Z:\03_혁신운영과\26) IoT과제 발굴심의 협의체\3.IoT 개발 과제\2511_선각1B공장 강재추적_DMIC\10. 영상기반\강재 AR부착사진\case_1"
DEFAULT_EXCEL_NAME = "barcode_results.xlsx"
THUMB_MAX_W = 900  # 썸네일 최대 가로폭(px)
IMAGE_CELL_ANCHOR = "F2"  # 엑셀 내 이미지 삽입 위치(좌상단 셀)

# 처리 대상 확장자
EXTS = ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.tif", "*.tiff")

# 기본 심볼 세트(필요시 조정)
SYMBOLS = [
    ZBarSymbol.QRCODE,
    ZBarSymbol.EAN13, ZBarSymbol.EAN8, ZBarSymbol.UPCA, ZBarSymbol.UPCE,
    ZBarSymbol.CODE128, ZBarSymbol.CODE39, ZBarSymbol.ITF, ZBarSymbol.CODABAR,
]


# ===== 유틸 =====
def load_image_any_path(path: str) -> Optional[np.ndarray]:
    """한글/공백 경로 안전 로드: np.fromfile + cv2.imdecode"""
    try:
        data = np.fromfile(path, dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def save_thumb(img_bgr: np.ndarray, save_path: str, max_w: int = THUMB_MAX_W) -> str:
    """썸네일 저장(PNG). 비율 유지 축소."""
    h, w = img_bgr.shape[:2]
    if w > max_w:
        ratio = max_w / float(w)
        new_size = (max_w, int(h * ratio))
        img_bgr = cv2.resize(img_bgr, new_size, interpolation=cv2.INTER_AREA)
    cv2.imencode(".png", img_bgr)[1].tofile(save_path)
    return save_path


def clean_sheet_name(name: str) -> str:
    """파일명 -> 엑셀 시트 허용 문자로 정리, 길이 31 제한"""
    base = os.path.splitext(name)[0]
    base = re.sub(r'[:\\/?*\[\]]', '_', base)
    return base[:31] or "sheet"


def bottom_y_of_decoded_like(rect: Tuple[int, int, int, int], polygon: Optional[List[Tuple[int, int]]]) -> float:
    if polygon and len(polygon) > 0:
        return float(max(y for _, y in polygon))
    x, y, w, h = rect
    return float(y + h)


@dataclass
class SimpleDecoded:
    type: str
    data: bytes
    rect: Tuple[int, int, int, int]
    polygon: Optional[List[Tuple[int, int]]]


def draw_overlay(img_bgr: np.ndarray, decoded_list: List[SimpleDecoded], code_info: List[Tuple[float, str, str]]):
    """디텍션 박스/라벨 + 정렬 기준선(max_y) 오버레이"""
    out = img_bgr.copy()
    H, W = out.shape[:2]

    for d in decoded_list:
        pts = d.polygon
        if pts and len(pts) >= 4:
            pts_np = np.array(pts, dtype=np.int32)
            cv2.polylines(out, [pts_np], isClosed=True, color=(0, 200, 0), thickness=3)
            mid = pts_np.mean(axis=0).astype(int)
            label_xy = (int(mid[0]), max(20, int(mid[1]) - 10))
        else:
            (x, y, w, h) = d.rect
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 200, 0), 3)
            label_xy = (x, max(20, y - 10))

        t = d.type
        val = d.data.decode("utf-8", "ignore")
        txt = f"{t}: {val[:40]}{'...' if len(val) > 40 else ''}"
        cv2.putText(out, txt, label_xy, cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 60, 255), 2, cv2.LINE_AA)

    for bottom_y, t, v in code_info:
        y = int(round(bottom_y))
        cv2.line(out, (0, y), (W - 1, y), (255, 180, 0), 2)
        tag = f"max_y={y}"
        cv2.putText(out, tag, (10, max(30, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 180, 0), 2, cv2.LINE_AA)

    return out


def enhance_for_barcode(img_bgr: np.ndarray) -> np.ndarray:
    """그레이 + CLAHE로 대비 향상(선택적 전처리)."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    eq = clahe.apply(gray)
    return cv2.cvtColor(eq, cv2.COLOR_GRAY2BGR)


def rotate_image(img: np.ndarray, k90: int) -> np.ndarray:
    if k90 % 4 == 0:
        return img
    if k90 % 4 == 1:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if k90 % 4 == 2:
        return cv2.rotate(img, cv2.ROTATE_180)
    return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)


def map_point_back_from_rot(x: int, y: int, W: int, H: int, k90: int) -> Tuple[int, int]:
    k = k90 % 4
    if k == 0:
        return x, y
    if k == 1:  # 90 CW: x' = H-1 - y, y' = x -> inverse
        return y, H - 1 - x
    if k == 2:  # 180
        return W - 1 - x, H - 1 - y
    # 270 CW: x' = y, y' = W-1 - x -> inverse
    return W - 1 - y, x


def decode_with_rotations(img_bgr: np.ndarray, try_enhance: bool, rotations: List[int]) -> Tuple[List[SimpleDecoded], List[Tuple[float, str, str]]]:
    H, W = img_bgr.shape[:2]
    decoded_agg: List[SimpleDecoded] = []
    seen = set()

    candidates = [(0, img_bgr)]
    if try_enhance:
        candidates.append((0, enhance_for_barcode(img_bgr)))
    for k90 in rotations:
        if k90 % 4 == 0:
            continue
        rot_img = rotate_image(img_bgr, k90)
        candidates.append((k90, rot_img))
        if try_enhance:
            candidates.append((k90, enhance_for_barcode(rot_img)))

    for k90, img in candidates:
        dec = decode(img, symbols=SYMBOLS)
        if not dec:
            continue
        for d in dec:
            t = d.type
            v = d.data.decode("utf-8", "ignore")
            rect = (d.rect.left, d.rect.top, d.rect.width, d.rect.height)
            poly = None
            pts = getattr(d, "polygon", None)
            if pts and len(pts) >= 4:
                poly = [map_point_back_from_rot(p.x, p.y, W, H, k90) for p in pts]
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                rect = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
            else:
                x, y, w, h = rect
                x0, y0 = map_point_back_from_rot(x, y, W, H, k90)
                x1, y1 = map_point_back_from_rot(x + w, y + h, W, H, k90)
                rect = (min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))

            key = (t, v)
            btm = bottom_y_of_decoded_like(rect, poly)
            # 중복 제거(동일 타입+값): 더 큰 하단Y 우선
            replaced = False
            for i, sd in enumerate(decoded_agg):
                if sd.type == t and sd.data.decode("utf-8", "ignore") == v:
                    prev_btm = bottom_y_of_decoded_like(sd.rect, sd.polygon)
                    if btm > prev_btm:
                        decoded_agg[i] = SimpleDecoded(t, v.encode("utf-8"), rect, poly)
                    replaced = True
                    break
            if not replaced:
                decoded_agg.append(SimpleDecoded(t, v.encode("utf-8"), rect, poly))

    code_info: List[Tuple[float, str, str]] = []
    for sd in decoded_agg:
        v = sd.data.decode("utf-8", "ignore")
        code_info.append((bottom_y_of_decoded_like(sd.rect, sd.polygon), sd.type, v))
    code_info.sort(reverse=True, key=lambda x: x[0])

    return decoded_agg, code_info


def collect_images(image_dir: str) -> List[str]:
    files = []
    for pat in EXTS:
        files.extend(glob.glob(os.path.join(image_dir, pat)))
    return files


def main():
    parser = argparse.ArgumentParser(description="바코드/QR 하단 Y 좌표 계산 및 엑셀 리포트")
    parser.add_argument("--dir", dest="image_dir", default=DEFAULT_IMAGE_DIR, help="이미지 폴더 경로")
    parser.add_argument("--excel", dest="excel_name", default=DEFAULT_EXCEL_NAME, help="엑셀 파일명")
    parser.add_argument("--no-overlay", action="store_true", help="엑셀 썸네일에 오버레이 미적용")
    parser.add_argument("--thumb-max-w", type=int, default=THUMB_MAX_W, help="썸네일 최대 가로폭(px)")
    parser.add_argument("--enhance", action="store_true", help="그레이/CLAHE 전처리 시도")
    parser.add_argument("--try-rot", default="all", choices=["none", "90", "180", "270", "all"], help="추가 회전 탐색")
    args = parser.parse_args()

    image_dir = args.image_dir
    excel_path = os.path.join(image_dir, args.excel_name)
    thumb_dir = os.path.join(image_dir, "_excel_thumbs")
    os.makedirs(thumb_dir, exist_ok=True)

    rotations = []
    if args.try_rot == "all":
        rotations = [1, 2, 3]
    elif args.try_rot == "none":
        rotations = []
    else:
        rotations = [{"90": 1, "180": 2, "270": 3}[args.try_rot]]

    files = collect_images(image_dir)
    if not files:
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_dir}")

    rows: List[List[object]] = []
    thumb_for_file: dict = {}

    for f in files:
        img = load_image_any_path(f)
        fname = os.path.basename(f)

        print(f"\n=== {fname} ===")
        if img is None:
            print("[경고] 이미지 로드 실패")
            rows.append([fname, None, None, None, None])
            continue

        decoded_list, code_info = decode_with_rotations(img, try_enhance=args.enhance, rotations=rotations)

        if not code_info:
            print("바코드/QR 미검출")
            rows.append([fname, None, None, None, None])
            thumb_path = os.path.join(thumb_dir, Path(fname).stem + "_thumb.png")
            save_thumb(img, thumb_path, args.thumb_max_w)
            thumb_for_file[fname] = thumb_path
            continue

        for idx, (btm_y, t, v) in enumerate(code_info):
            show_val = v if len(v) <= 80 else (v[:80] + "...")
            print(f"{idx:02d}\tTYPE={t}\tmax_y={btm_y:.2f}\tVAL={show_val}")
            rows.append([fname, f"{idx:02d}", t, v, btm_y])

        overlay_img = img if args.no_overlay else draw_overlay(img, decoded_list, code_info)
        thumb_path = os.path.join(thumb_dir, Path(fname).stem + ("_thumb.png" if args.no_overlay else "_overlay_thumb.png"))
        save_thumb(overlay_img, thumb_path, args.thumb_max_w)
        thumb_for_file[fname] = thumb_path

    df = pd.DataFrame(rows, columns=["파일명", "순번", "바코드종류", "값", "하단Y좌표"])

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        # (1) 전체 결과 시트
        df.to_excel(writer, sheet_name="all_results", index=False)
        ws_all = writer.sheets["all_results"]
        ws_all.freeze_panes = "A2"
        ws_all.column_dimensions["A"].width = 40  # 파일명
        ws_all.column_dimensions["B"].width = 8   # 순번
        ws_all.column_dimensions["C"].width = 14  # 바코드종류
        ws_all.column_dimensions["D"].width = 60  # 값
        ws_all.column_dimensions["E"].width = 14  # 하단Y좌표

        # (2) 파일별 시트 + 썸네일 삽입
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

            ws.column_dimensions["A"].width = 40
            ws.column_dimensions["B"].width = 8
            ws.column_dimensions["C"].width = 14
            ws.column_dimensions["D"].width = 60
            ws.column_dimensions["E"].width = 14

            img_path = thumb_for_file.get(fname)
            if img_path and os.path.exists(img_path):
                try:
                    xlimg = XLImage(img_path)
                    ws.add_image(xlimg, IMAGE_CELL_ANCHOR)
                except Exception as e:
                    print(f"[이미지 삽입 실패] {fname}: {e}")

    print(f"\n엑셀 저장 완료: {excel_path}")
    print(f"썸네일 폴더: {thumb_dir}")


if __name__ == "__main__":
    main()

