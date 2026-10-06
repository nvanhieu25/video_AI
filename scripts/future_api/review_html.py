#!/usr/bin/env python3
"""[Phương án B — KHUNG] Tạo trang HTML dạng lưới xem tất cả clip của tập để duyệt (Cổng 4).

Dùng (tương lai): python3 scripts/future_api/review_html.py E01
"""
import sys

from _common import plan_b_not_enabled

# TODO: quét episodes/EXX/clips/*.mp4, nhóm theo shot (nhiều phiên bản / shot)
# TODO: mỗi ô: <video> 9:16, số shot, prompt, hành động, camera, thoi_luong_s
# TODO: kèm checklist từ skills/qc_checklist.md để người duyệt đánh dấu
# TODO: ghi episodes/EXX/review.html (HTML tĩnh, không cần server)


def main(argv):
    plan_b_not_enabled("review_html")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
