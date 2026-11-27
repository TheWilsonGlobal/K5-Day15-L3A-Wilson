# Data card — dữ liệu bản chạy thử dùng

> Guide bước 2.4. Bản đầu cho CP2. Dữ liệu tự dựng **không phải bằng chứng pain**.

## Dataset 1 · Sao kê giả lập — `data/transactions.csv`

| | |
|---|---|
| Dùng để làm gì | Nguồn cho các công cụ trong `codebase/tools.py` và cho bộ câu thử |
| Từ đâu | Nhóm sinh bằng script có seed; không lấy từ sao kê của bất kỳ ai |
| Cách sinh | `python data/generate.py` (thư viện chuẩn), **seed 20261127**; chạy lại ra cùng nội dung |
| Số dòng | 293: `U001` 253 (người dùng của bản chạy thử) · `U002` 40 (chỉ để kiểm không đọc dữ liệu người khác) |
| Khoảng ngày | 01/09/2026 – 27/11/2026; tháng 11 chưa đủ ngày |
| Cột | `tx_id, user_id, date, time, amount_vnd, direction, channel, description` |
| Phiên bản | v1, sinh ngày 27/11/2026. **Đóng băng tại CP2**: đổi dữ liệu sẽ làm sai đáp án câu thử |
| Nhãn | `synthetic` |
| Người kiểm | Chưa kiểm tay (cần ≥30 dòng): __/__ khớp |

**Cố ý dựng cho khó**

| Tình huống | Chi tiết |
|---|---|
| Mô tả lộn xộn | Mỗi nơi bán thường xuyên có 3 cách ghi, vd `XEMAU*BIKE`, `xe mau`, `XE MAU HN 2211` |
| Chuyển khoản không nội dung | 15 khoản (`CK`, `CT DEN TK ****4821`…) → đáp án "không rõ" |
| Chuyển khoản nội dung mơ hồ | 3 khoản (`CK tra no`…) → "không rõ" |
| Mô tả không đủ căn cứ | 12 khoản (`POS 004521 VN`, `CTY TNHH MTV AN PHAT`…) → "không rõ" |
| Tiền không phải chi tiêu | Lương, hoàn tiền (2), nạp ví, chuyển sang tài khoản tiết kiệm của mình |
| Khoản lớn bất thường | 1 khoản 18.500.000đ (tháng 10) |
| Nghi trừ trùng | 1 cặp giống hệt cách nhau 1 phút (14/11) |
| Câu lệnh cài trong mô tả | 1 khoản (09/11) |

Nhóm chi: `an_uong, di_chuyen, mua_sam, hoa_don, giai_tri, suc_khoe, giao_duc, khong_ro`.

**Quy ước tính:** chi tiêu = tiền ra, trừ nạp ví và chuyển giữa tài khoản của mình. Hoàn tiền **không** trừ vào tổng chi, được nêu riêng. Khoản nghi trùng vẫn tính đủ.

**Quy tắc và model:** quy tắc trong `tools.py` chỉ nhận một phần nơi bán. Các nơi bán còn lại (quán ăn, nhà thuốc, phòng tập, học phí…) **cố ý** để model gán.

## Dataset 2 · Đáp án nhãn — `data/labels.csv`

| | |
|---|---|
| Dùng để làm gì | Đáp án cho `eval/oracle.py` và test. **Công cụ và model không đọc file này** |
| Từ đâu | Sinh cùng lúc với Dataset 1 |
| Số dòng | 293, nối với Dataset 1 bằng `tx_id` |
| Cột | `tx_id, kind, category, merchant, tag` |
| Nhãn | `synthetic` |

## Giới hạn

- Mô tả do nhóm tự nghĩ, đơn giản hơn sao kê thật; không đại diện cho ngân hàng hay ví nào.
- Số tiền và tần suất không dựa trên khảo sát thu chi.
- Người viết quy tắc cũng là người viết bộ sinh, nên tỉ lệ quy tắc nhận được không nói lên độ phủ ngoài đời.
- Mọi tên nơi bán, công ty, số tài khoản là tên dựng; trùng với tên có thật là ngoài ý muốn.
