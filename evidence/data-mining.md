# Đào data — cách đếm và kết quả

> Guide bước 1.2. Mục 1 viết lúc 10:30 Thứ Sáu 27/11/2026, **trước khi đọc review đầu tiên**. Nếu phải đổi cách đếm, ghi thêm dòng "đã đổi", không xoá dòng cũ.
> Repo chỉ chứa số đã tổng hợp, trích ngắn đã bỏ tên và link nguồn.

## 1. Cách đếm — viết TRƯỚC khi chạy

**Nguồn và cách lấy mẫu**

- App: MoMo, ZaloPay và 1 app ngân hàng số (nhóm ghi tên app **trước khi đọc**: ________).
- Kho: Google Play (ngôn ngữ Việt, sắp theo "Mới nhất"). App nào không đủ thì lấy thêm App Store Việt Nam và ghi rõ.
- Mẫu: **15 review mới nhất có phần chữ** của mỗi app, **mọi mức sao**, tính ngược từ thời điểm lấy → N = 45 (tối thiểu 30). Không bỏ review nào vì nội dung; chỉ bỏ review trống hoặc chỉ có biểu tượng, và ghi số đã bỏ.
- Không lọc theo từ khoá. Nếu sau đó lấy thêm mẫu lọc từ khoá (sao kê, lịch sử giao dịch, chi tiêu) thì đếm **riêng**, không gộp vào N.

**Đếm gì**

- **Câu hỏi chính:** trong N review, bao nhiêu review kể khó khăn khi **xem, hiểu hoặc tổng hợp** lịch sử giao dịch, chi tiêu của chính mình.
- **Mẫu số:** toàn bộ N review đã đọc và gắn nhãn, kể cả review không liên quan.
- Một review một nhãn chính. Review khớp nhiều nhãn thì lấy nhãn đứng trên trong bảng.

**Nhãn nháp** (đọc khoảng 30 review rồi mới chốt; mọi thay đổi ghi vào mục "Đã đổi")

| Nhãn | Định nghĩa | Tính vào số chính? |
|---|---|---|
| `kho_hieu_gd` | Không hiểu một giao dịch là gì, ở đâu, vì sao bị trừ tiền | Có |
| `kho_tong_hop` | Muốn biết tổng chi, chi theo nhóm hoặc theo thời gian mà không làm được hay phải tự cộng | Có |
| `kho_tim_gd` | Khó tìm, lọc, xem lại hoặc xuất lịch sử giao dịch | Có |
| `ngan_sach` | Biết vượt ngân sách quá muộn, muốn được nhắc (hướng E2) | Đếm riêng |
| `gd_bi_chan` | Giao dịch bị tạm giữ, bị chặn, nghi lừa đảo (hướng E3) | Đếm riêng |
| `khac` | Mọi nội dung còn lại | Không |

**Bảng gắn nhãn:** `evidence/reviews.csv`, cột `ma,app,kho,link,ngay_xem,ngay_review,so_sao,trich,nhan,nguoi_gan`. `trich` tối đa 2 câu, bỏ tên người viết, số điện thoại, số tài khoản.

**Kiểm nhãn:** người thứ hai gắn nhãn độc lập 10 review, ghi số khớp x/10.

- Script / công thức: `evidence/count.py` (viết khi có `reviews.csv`).

**Đã đổi** (thời điểm · đổi gì · vì sao): chưa có.

## 2. Đọc trước, đếm sau

Chưa đọc.

## 3. Kết quả

Chưa có số liệu.

| Đếm gì | x / N | % | Ghi chú |
|---|---|---|---|
| | | | |

## 4. ≥5 ví dụ cụ thể (mã review, đã bỏ tên)

Chưa có.

## 5. Giới hạn của data

- Người viết review thường đang bực, nên % trong review không phải % của mọi người dùng.
- Review app thiên về lỗi đăng nhập, chuyển tiền; khó khăn khi tổng hợp chi tiêu có thể ít được viết ra.
- Review không cho biết người viết có đúng vai người dùng chính hay không.

→ Kiểm lại bằng phỏng vấn (`evidence/interviews/`).
