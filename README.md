# richesse-ai-drama

Quy trình sản xuất phim ngắn AI nhiều tập (dọc 9:16, TikTok/Reels) có đặt sản phẩm RICHESSE.

- **Phương án A (đang dùng):** tự động phần chữ — kịch bản → shot list → bảng thoại → prompt. Clip được tạo thủ công trên Dreamina bởi đối tác từ file `handoff.md`.
- **Phương án B (để sẵn):** tự động tạo voice/clip qua API (`scripts/future_api/`). Hiện chỉ là khung TODO, không gọi API, không cần key.

## Quy trình 13 bước

| # | Bước | Đầu ra | Cổng duyệt |
|---|------|--------|-----------|
| 1 | Viết series bible | `bible/series_bible.md` | |
| 2 | Khóa nhân vật: ảnh chuẩn, câu mô tả cố định, voice_id | `bible/characters/*.md`, `assets/refs/` | ✅ **Cổng 2 — khóa nhân vật** |
| 3 | Viết kịch bản tập | `episodes/EXX/script.md` | ✅ **Cổng 1 — kịch bản** |
| 4 | Tách shot list | `episodes/EXX/shots.csv` | |
| 5 | Kiểm tra shot list, tách shot bị SPLIT | `validate_shots.py` | |
| 6 | Storyboard / khung hình đầu mỗi shot | ảnh tham chiếu theo shot | ✅ **Cổng 3 — storyboard** |
| 7 | Bảng thoại | `episodes/EXX/dialogue.csv` | |
| 8 | Thu/tạo voice, **chốt thời lượng** từng shot | `voice/*.wav`, cột `thoi_luong_s` | |
| 9 | Viết prompt (theo `skills/prompt_writer.md`, tra `prompt_lib/`) | cột `prompt` trong `shots.csv` | |
| 10 | Xuất handoff, tạo clip trên Dreamina, ghi log | `handoff.md`, `log.csv` | |
| 11 | QC từng clip (`skills/qc_checklist.md`) | clip đạt | ✅ **Cổng 4 — clip** |
| 12 | Dựng: ghép clip, voice, nhạc, chèn footage sản phẩm thật | bản dựng | |
| 13 | Final review (`skills/final_review.md`) rồi đăng | bản cuối | ✅ **Cổng 5 — bản cuối** |

Không được bỏ qua cổng duyệt. Voice luôn được chốt **trước** khi tạo clip (thời lượng clip theo thoại).
Prompt hay (đạt nhiều lần) được lưu vào `prompt_lib/library.csv` và tăng `so_lan_dat`.

## Chạy Phương án A

Yêu cầu: Python 3.10+ (chỉ thư viện chuẩn).

```bash
# 1. Tạo tập mới từ template
cp -r templates episodes/E02

# 2. Điền shots.csv, dialogue.csv rồi kiểm tra
python3 scripts/validate_shots.py episodes/E02/shots.csv

# 3. Khi không còn lỗi/SPLIT, xuất file bàn giao cho đối tác
python3 scripts/build_handoff.py E02
#   → episodes/E02/handoff.md  (bảng shot + prompt để copy vào Dreamina)
```

`validate_shots.py` kiểm tra mỗi shot: 1 hành động, 1 chuyển động camera, prompt ≤ 60 từ, không tả ngoại hình, không để AI vẽ logo/chữ, `loai_shot` hợp lệ. Shot nhồi nhiều hành động bị báo **SPLIT** kèm gợi ý cách tách. Mã thoát khác 0 nếu có vấn đề.

`build_handoff.py` từ chối xuất nếu shot list chưa qua kiểm tra (dùng `--force` để bỏ qua — không khuyến khích).

### Giá trị `loai_shot`
- `AI` — clip AI không thoại
- `AI+lipsync` — clip AI có khẩu hình theo voice
- `san_pham_that` — ảnh/video thật của RICHESSE, **không** tạo bằng AI
- `cutaway` — cảnh chèn (AI hoặc stock), không nhân vật nói

## Cấu trúc

```
bible/          series bible, nhân vật, quy tắc sản phẩm
skills/         system prompt viết prompt, checklist QC, final review
prompt_lib/     thư viện prompt đã chứng minh hiệu quả
templates/      shots.csv, dialogue.csv, log.csv rỗng
episodes/EXX/   mỗi tập một thư mục (E01 là ví dụ)
assets/         ảnh nhân vật/bối cảnh đã khóa, ảnh/video sản phẩm thật
scripts/        validate_shots.py, build_handoff.py, future_api/ (Phương án B)
```

## Phương án B (chưa bật)
Xem `scripts/future_api/`. Cần `.env` (copy từ `.env.example`). Chỉ bật khi được yêu cầu rõ, luôn tuân `BUDGET_PER_EPISODE_USD` và `MAX_RETRIES_PER_SHOT`.
