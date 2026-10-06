# QC checklist — duyệt từng clip (Cổng 4)

Đánh dấu từng mục. Một mục ❌ → tạo lại (ghi `log.csv` với `loai_loi`), tối đa `MAX_RETRIES_PER_SHOT` lần, sau đó báo người duyệt.

| Hạng mục | Kiểm tra | loai_loi |
|----------|----------|----------|
| Mặt | Giống ảnh chuẩn, không biến dạng, không đổi người giữa clip | `mat` |
| Tóc | Kiểu, màu, độ dài giống ảnh chuẩn | `mat` |
| Trang phục | Đúng bộ, đúng màu, không mọc thêm/mất chi tiết | `mat` |
| Bối cảnh | Khớp ảnh bối cảnh đã khóa, ánh sáng nhất quán với shot trước/sau | `meo` |
| Tay chân | Đủ ngón, không thừa tay, khớp không gãy | `meo` |
| Chuyển động | Đúng 1 hành động như shot list, tốc độ tự nhiên, không giật/trôi | `hanh_dong` |
| Camera | Đúng chuyển động camera đã ghi, không tự zoom/đổi góc | `camera` |
| Khẩu hình | (AI+lipsync) khớp voice, không lệch > 2 khung hình | `hanh_dong` |
| Sản phẩm | Không có logo/chữ do AI vẽ; hình dạng/màu đúng; shot cận dùng footage thật | `san_pham` |
| Thời lượng | Đủ `thoi_luong_s` + khoảng đệm để cắt | `hanh_dong` |
| Lỗi lạ | Vật thể biến hình, chữ rác, nhấp nháy | `meo` |
