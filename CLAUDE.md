# CLAUDE.md — Quy tắc làm việc cho agent

Dự án: phim ngắn AI nhiều tập (9:16, TikTok/Reels) có đặt sản phẩm RICHESSE.
Giai đoạn hiện tại: **Phương án A** (tự động phần chữ). Phương án B (`scripts/future_api/`) chỉ là khung — chưa được bật.

## Quy tắc bắt buộc
- Thứ tự bắt buộc: kịch bản → shot list → bảng thoại/voice (chốt thời lượng) → prompt. Voice luôn trước tạo clip.
- Cổng người duyệt: kịch bản, khóa nhân vật, storyboard, clip, bản cuối. Không tự bỏ qua cổng.
- Mỗi nhân vật chỉ một nguồn giọng (MiniMax voice_id ghi trong bible).
- Không bao giờ để AI tạo logo/chữ trên sản phẩm RICHESSE.
- Không gọi API trả phí khi chưa được yêu cầu rõ; luôn tôn trọng BUDGET_PER_EPISODE_USD và MAX_RETRIES_PER_SHOT.
- Không ghi API key vào code hay chat; chỉ đọc từ .env.
- Nếu một tác vụ chạy quá 10 phút mà chưa có kết quả rõ ràng: dừng, báo tình trạng và hỏi tôi có tiếp tục không.

## Quy ước kỹ thuật
- Chỉ dùng thư viện chuẩn Python (csv, pathlib, ...). Không cài thư viện ngoài khi chưa hỏi.
- CSV đọc bằng `utf-8-sig` (chịu được file lưu từ Excel), ghi bằng `utf-8`.
- Viết prompt video theo `skills/prompt_writer.md`; chạy `scripts/validate_shots.py` sau mỗi lần sửa `shots.csv`.
- Shot `san_pham_that` dùng ảnh/video thật trong `assets/product/` — không viết prompt AI cho shot này (xem `bible/product_rules.md`).
- Ghi mọi lần tạo clip vào `episodes/EXX/log.csv`.
