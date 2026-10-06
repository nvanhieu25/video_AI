#!/usr/bin/env python3
"""[Phương án B — KHUNG] Ghép clip đã duyệt + voice + nhạc bằng ffmpeg.

Dùng (tương lai): python3 scripts/future_api/assemble.py E01
"""
import sys

from _common import plan_b_not_enabled

# TODO: kiểm tra ffmpeg có sẵn (shutil.which) — không tự cài
# TODO: lấy clip đã duyệt theo thứ tự shots.csv (trang_thai = duyet); san_pham_that lấy từ assets/product/
# TODO: cắt mỗi clip đúng thoi_luong_s, chuẩn hóa 1080x1920, fps cố định
# TODO: concat → ghép voice/*.wav đúng mốc → nhạc nền (đã có giấy phép) giảm âm dưới thoại
# TODO: xuất episodes/EXX/renders/EXX_draft.mp4 rồi chuyển sang final_review (Cổng 5)


def main(argv):
    plan_b_not_enabled("assemble")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
