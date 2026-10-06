#!/usr/bin/env python3
"""[Phương án B — KHUNG] dialogue.csv → voice/*.wav → cập nhật thoi_luong_s.

Dùng (tương lai): python3 scripts/future_api/tts_minimax.py E01
CHƯA GỌI API. Cần MINIMAX_API_KEY trong .env khi triển khai.
"""
import sys

from _common import plan_b_not_enabled

# TODO: đọc episodes/EXX/dialogue.csv (utf-8-sig)
# TODO: với mỗi dòng, lấy voice_id của nhan_vat từ bible/characters/<nhan_vat>.md (một nhân vật = một voice_id)
# TODO: gọi MiniMax TTS (cam_xuc, toc_do, ghi_chu_phat_am) → episodes/EXX/voice/<shot>_<n>.wav
# TODO: đo thời lượng wav (module chuẩn `wave`) → ghi file_audio, thoi_luong_s vào dialogue.csv
# TODO: cập nhật thoi_luong_s trong shots.csv = tổng thoại của shot + đệm
# TODO: ghi chi phí vào log.csv; dừng nếu vượt BUDGET_PER_EPISODE_USD


def main(argv):
    plan_b_not_enabled("tts_minimax")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
