#!/usr/bin/env python3
"""[Phương án B — KHUNG] BytePlus ModelArk (Seedance): upload ảnh → tạo task → chờ → tải clip.

Dùng (tương lai): python3 scripts/future_api/run_seedance.py E01 [--shot 3]
CHƯA GỌI API. Cần ARK_API_KEY trong .env khi triển khai.
"""
import re
import sys

from _common import plan_b_not_enabled


def refs_to_image_tokens(prompt):
    """Đổi @ten_anh trong prompt thành [Image1], [Image2]... theo thứ tự xuất hiện.

    Trả về (prompt_moi, danh_sach_ten_anh) để upload ảnh đúng thứ tự. Hàm thuần, không gọi mạng.
    """
    names = []

    def repl(m):
        name = m.group(1)
        if name not in names:
            names.append(name)
        return f"[Image{names.index(name) + 1}]"

    return re.sub(r"@([\w.-]+)", repl, prompt), names


# TODO: đọc shots.csv; chỉ xử lý loai_shot AI / AI+lipsync / cutaway có trang_thai cho phép
# TODO: bỏ qua san_pham_that (không bao giờ tạo sản phẩm bằng AI)
# TODO: refs_to_image_tokens(prompt) → upload ảnh assets/refs/<ten_anh>.* theo thứ tự
# TODO: tạo task (9:16, duration = thoi_luong_s), poll trạng thái có timeout
#       (>10 phút không có kết quả rõ ràng → dừng và hỏi người dùng)
# TODO: tải clip về episodes/EXX/clips/<shot>_v<n>.mp4
# TODO: ghi log.csv (so_lan_tao, chi_phi); dừng khi vượt MAX_RETRIES_PER_SHOT hoặc BUDGET_PER_EPISODE_USD


def main(argv):
    plan_b_not_enabled("run_seedance")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
