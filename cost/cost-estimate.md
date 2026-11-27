# Chi phí khi dùng thật

> Guide bước 4.2, nộp ở CP4 14:30 Thứ Bảy 28/11. Chấm ở rubric R6.
> Số **không điền tay**: `python run.py simulate --rate-from eval/run-2.csv` → chép bảng trong `cost/simulate-N-summary.md` vào đây.
> **Chưa chạy lượt mô phỏng chính thức.** Lúc build dùng gói miễn phí vẫn tính theo giá gói trả phí.

## 1. Đầu vào

**Persona** (`cost/personas.yaml`; tỉ lệ và tần suất hiện *(tự ước tính)*, [CHỜ DỮ LIỆU THẬT: số từ phỏng vấn]):

| Persona | Tỉ lệ | Phiên / người / tháng | Lượt hỏi / phiên | Hỏi gì |
|---|---:|---:|---:|---|
| `xem_cuoi_thang` | 0,50 | 2 | 1 | Tổng quan tháng |
| `theo_doi_hang_tuan` | 0,35 | 5 | 2 | Theo tuần, nhóm, nơi bán |
| `so_sanh_nhieu_thang` | 0,15 | 3 | 3 | Khoảng dài, so tháng (token vào lớn hơn) |

**Số người dùng:** thấp 3.000 · cơ sở 30.000 · cao 300.000 *(tự ước tính: 0,01% / 0,1% / 1%)* của hơn 30 triệu người dùng MoMo ([Báo Đại biểu Nhân dân, 28/11/2025](https://daibieunhandan.vn/momo-ky-niem-15-nam-nguoi-khong-lo-fintech-viet-nam-dat-30-trieu-nguoi-dung-cong-nghe-ai-lam-chu-loi-van-hanh-10397472.html), xem 27/11/2026; bài không nêu nguồn kiểm độc lập).

**Giá** (USD / 1 triệu token, [bảng giá](https://ai.google.dev/gemini-api/docs/pricing), BTC tra 25/11/2026 trong `further-reading/model-prices.md`):

| Model | Vào | Ra (gồm token suy nghĩ) | Ghi chú |
|---|---:|---:|---|
| `gemini-3.5-flash-lite` | 0,30 | 2,50 | Model đang dùng để đo token |
| `gemini-3.8-flash` | 1,50 | 7,50 | Giá từ 01/01/2027; chỉ nhân giá, chưa chạy thật |

**Tỉ lệ đạt dùng để tính:** [CHỜ DỮ LIỆU THẬT: x/y (%) của lượt `run-2`]
**Đo token trên** `gemini-3.5-flash-lite`, **tính giá** cả hai model. Hãng tách token như nhau trong cùng họ hay không: chưa kiểm.

## 2. Kết quả mô phỏng

Lượt mô phỏng: [CHỜ DỮ LIỆU THẬT: `cost/simulate-N.csv` · run ID · số phiên (≥50) · seed 42]

| Model | Chi phí / phiên | Chi phí / task thành công | / tháng — thấp | / tháng — cơ sở | / tháng — cao | / người / tháng (cơ sở) |
|---|---|---|---|---|---|---|
| `gemini-3.5-flash-lite` | [CHỜ DỮ LIỆU THẬT] | | | | | |
| `gemini-3.8-flash` | [CHỜ DỮ LIỆU THẬT] | | | | | |

Công thức:

- chi phí / phiên = (token vào × giá vào + token ra × giá ra) ÷ 1.000.000
- chi phí / task thành công = chi phí trung bình mỗi phiên ÷ tỉ lệ đạt — **không coi như đạt 100%**
- chi phí / tháng = Σ persona (người dùng × tỉ lệ × phiên / tháng × chi phí / phiên của persona)

## 3. So với impact

- Impact / người gặp pain / tháng (`spec.md` §2, f × t): [CHỜ DỮ LIỆU THẬT] phút
- Quy ra tiền (nếu làm): giá trị một phút [CHỜ DỮ LIỆU THẬT: nguồn thu nhập hoặc ghi *(tự ước tính)*]; tỷ giá [CHỜ DỮ LIỆU THẬT: nguồn]
- Chi phí / người / tháng (cơ sở): [CHỜ DỮ LIỆU THẬT]
- **Kết luận một dòng — đáng làm không:** [CHỜ DỮ LIỆU THẬT]

## 4. Độ nhạy và ngoài phạm vi mô phỏng

| Cần gạt | Ảnh hưởng dự kiến | Số |
|---|---|---|
| Lưu nhãn của mô tả đã gán (bản chạy thử chưa lưu) | Bỏ phần lớn lời gọi gán nhóm lặp lại | [CHỜ DỮ LIỆU THẬT: tính từ token từng lời gọi trong trace mô phỏng] |
| Model mạnh hơn | Xem bảng mục 2 | [CHỜ DỮ LIỆU THẬT] |
| Nhiều giao dịch hơn | Chỉ phần gán nhóm tăng theo số **kiểu mô tả**, không theo số giao dịch | Chưa đo |

- Chi phí ngoài model (hosting, lưu trữ, kết nối dữ liệu ngân hàng, giờ người xử lý khiếu nại): chưa tính.
