#!/usr/bin/env python3
"""Kiểm tra shots.csv theo quy tắc của skills/prompt_writer.md.

Mỗi shot: 1 hành động, 1 chuyển động camera, prompt <= 60 từ, không tả ngoại hình/bối cảnh,
không để AI vẽ logo/chữ sản phẩm. Shot nhồi nhiều hành động được báo SPLIT kèm gợi ý tách.

Dùng:  python3 scripts/validate_shots.py episodes/E01/shots.csv
Mã thoát: 0 = sạch (có thể có cảnh báo), 1 = có LỖI hoặc SPLIT, 2 = không đọc được file.
"""
import csv
import re
import sys
from pathlib import Path

REQUIRED_COLUMNS = [
    "shot", "scene", "hanh_dong", "camera", "nhan_vat", "boi_canh", "thoai",
    "loai_shot", "thoi_luong_s", "prompt", "prompt_lib_id", "trang_thai",
]
SHOT_TYPES = {"AI", "AI+lipsync", "san_pham_that", "cutaway"}
AI_TYPES = {"AI", "AI+lipsync", "cutaway"}

MAX_PROMPT_WORDS = 60
TARGET_PROMPT_WORDS = 50
MAX_CLIP_SECONDS = 10
ENDING = "Keep face and outfit consistent with the reference."

# Từ nối cho thấy hơn một hành động / chuyển động camera (tiếng Việt + tiếng Anh).
CONNECTORS = re.compile(
    r"\s*(?:,|;|\+|\bvà\b|\brồi\b|\bsau đó\b|\bđồng thời\b|\btrong khi\b|\bxong\b"
    r"|\band then\b|\bthen\b|\band\b|\bwhile\b|\bafter that\b)\s*",
    re.IGNORECASE,
)
PROMPT_SEQUENCE = re.compile(r"\b(?:then|after that|afterwards|while|and then)\b", re.IGNORECASE)

CAMERA_TERMS = [
    "push-in", "push in", "pull-out", "pull out", "pull back", "dolly", "zoom", "pan",
    "tilt", "orbit", "tracking", "track", "crane", "handheld", "static", "locked-off",
    "truck", "whip", "arc",
]
APPEARANCE_TERMS = [
    "hair", "hairstyle", "ponytail", "bangs", "blonde", "brunette",
    "freckles", "makeup", "beard", "wearing", "wears", "dressed", "dress", "shirt", "blouse",
    "jacket", "suit", "skirt", "jeans", "outfit", "clothes", "clothing", "earrings",
    "necklace", "beautiful", "handsome", "pretty", "room", "bedroom", "kitchen", "office",
    "apartment", "wallpaper", "furniture", "interior", "decor",
]
PRODUCT_TEXT_TERMS = ["logo", "label", "text", "lettering", "brand", "packaging", "richesse", "writing"]
ABSTRACT_EMOTIONS = [
    "sad", "happy", "angry", "nervous", "scared", "afraid", "excited", "upset", "shocked",
    "emotional", "anxious", "jealous", "heartbroken", "furious", "joyful", "depressed",
]


def _find_terms(text, terms):
    return sorted({t for t in terms if re.search(rf"(?<![\w-]){re.escape(t)}(?![\w-])", text, re.IGNORECASE)})


def _parts(text):
    return [p.strip() for p in CONNECTORS.split(text or "") if p and p.strip()]


def check_row(row):
    """Trả về (errors, splits, warnings) cho một dòng shot."""
    errors, splits, warnings = [], [], []
    shot = (row.get("shot") or "?").strip()
    loai = (row.get("loai_shot") or "").strip()
    prompt = (row.get("prompt") or "").strip()

    if loai not in SHOT_TYPES:
        errors.append(f"loai_shot '{loai}' không hợp lệ (chỉ {', '.join(sorted(SHOT_TYPES))})")

    actions = _parts(row.get("hanh_dong"))
    if not actions:
        errors.append("thiếu hanh_dong")
    elif len(actions) > 1:
        suggestion = " | ".join(f"{shot}{chr(97 + i)}: {a}" for i, a in enumerate(actions))
        splits.append(f"{len(actions)} hành động → gợi ý tách: {suggestion}")

    cams = _parts(row.get("camera"))
    if not cams:
        errors.append("thiếu camera")
    elif len(cams) > 1:
        errors.append(f"{len(cams)} chuyển động camera ({' / '.join(cams)}) — chỉ được 1")

    dur = (row.get("thoi_luong_s") or "").strip()
    if dur:
        try:
            if float(dur) > MAX_CLIP_SECONDS:
                warnings.append(f"thoi_luong_s={dur}s > {MAX_CLIP_SECONDS}s — nên tách shot")
        except ValueError:
            errors.append(f"thoi_luong_s '{dur}' không phải số")

    if loai == "san_pham_that":
        if prompt:
            errors.append("shot san_pham_that phải dùng ảnh/video thật — xóa prompt AI")
        return errors, splits, warnings

    if loai == "AI+lipsync" and not (row.get("thoai") or "").strip():
        warnings.append("AI+lipsync nhưng cột thoai trống")

    if not prompt:
        if loai in AI_TYPES:
            warnings.append("chưa có prompt")
        return errors, splits, warnings

    if prompt.upper().startswith("SPLIT:"):
        splits.append(f"prompt_writer trả về {prompt}")
        return errors, splits, warnings

    words = len(prompt.split())
    if words > MAX_PROMPT_WORDS:
        errors.append(f"prompt {words} từ > {MAX_PROMPT_WORDS}")
    elif words > TARGET_PROMPT_WORDS:
        warnings.append(f"prompt {words} từ > mục tiêu {TARGET_PROMPT_WORDS}")

    body = prompt.replace(ENDING, "")
    if ENDING not in prompt:
        warnings.append(f'prompt chưa kết thúc bằng "{ENDING}"')

    looks = _find_terms(body, APPEARANCE_TERMS)
    if looks:
        errors.append(f"prompt tả ngoại hình/bối cảnh: {', '.join(looks)} (ảnh tham chiếu đã quyết định)")

    text_terms = _find_terms(body, PRODUCT_TEXT_TERMS)
    if text_terms:
        errors.append(f"prompt nhắc logo/chữ sản phẩm: {', '.join(text_terms)} — AI không được vẽ logo/chữ RICHESSE")

    cam_terms = _find_terms(body, CAMERA_TERMS)
    if len(cam_terms) > 1:
        errors.append(f"prompt có nhiều chuyển động camera: {', '.join(cam_terms)}")
    elif not cam_terms:
        warnings.append("prompt không thấy chuyển động camera rõ ràng")

    seq = PROMPT_SEQUENCE.findall(body)
    if seq:
        splits.append(f"prompt có chuỗi hành động ('{seq[0]}') — tách thành nhiều shot")

    emotions = _find_terms(body, ABSTRACT_EMOTIONS)
    if emotions:
        warnings.append(f"cảm xúc trừu tượng ({', '.join(emotions)}) — đổi thành dấu hiệu cơ thể")

    return errors, splits, warnings


def load_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"thiếu cột: {', '.join(missing)}")
        return list(reader)


def validate(path):
    """Trả về danh sách (row, errors, splits, warnings)."""
    return [(row, *check_row(row)) for row in load_rows(path)]


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    path = Path(argv[1])
    try:
        results = validate(path)
    except (OSError, ValueError) as e:
        print(f"Không đọc được {path}: {e}")
        return 2

    n_err = n_split = n_warn = 0
    print(f"Kiểm tra {path} — {len(results)} shot\n")
    for row, errors, splits, warnings in results:
        status = "SPLIT" if splits else ("LỖI" if errors else ("CẢNH BÁO" if warnings else "OK"))
        print(f"[{status:^8}] shot {row.get('shot', '?')} ({row.get('loai_shot', '')})")
        for msg in splits:
            print(f"    SPLIT  : {msg}")
        for msg in errors:
            print(f"    LỖI    : {msg}")
        for msg in warnings:
            print(f"    lưu ý  : {msg}")
        n_err += bool(errors)
        n_split += bool(splits)
        n_warn += bool(warnings)

    print(f"\nTổng: {len(results)} shot · {n_split} cần SPLIT · {n_err} có lỗi · {n_warn} có cảnh báo")
    return 1 if (n_err or n_split) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
