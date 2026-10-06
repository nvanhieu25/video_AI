# Quy tắc sản phẩm RICHESSE

1. **Shot cận sản phẩm luôn dùng ảnh/video thật** (`assets/product/`), đánh dấu `loai_shot = san_pham_that` trong `shots.csv`. Không viết prompt AI cho shot này.
2. **Không bao giờ để AI vẽ logo, chữ, nhãn, bao bì RICHESSE.** AI tạo ra chữ méo/sai logo → vi phạm nhận diện thương hiệu.
3. Trong shot AI có sản phẩm xuất hiện xa/mờ: prompt không nhắc "logo", "label", "text", "RICHESSE". Ưu tiên bố cục để sản phẩm quay lưng/ngoài khung, rồi chèn shot thật.
4. Màu, hình dạng bao bì phải khớp ảnh thật; nếu clip AI làm sai sản phẩm → loại clip (lỗi `san_pham` trong `log.csv`).
5. Mọi câu thoại nói về công dụng phải nằm trong "Claim được phép" của `series_bible.md`.
6. Tên file asset sản phẩm: `<ma_sp>_<goc>_<so>.jpg|mp4`, ví dụ `RCH01_front_01.jpg`. Ghi nguồn & quyền sử dụng trong `assets/product/README.md` khi có.
