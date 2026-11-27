# Chi phí khi dùng thật

> Guide bước 4.2, nộp ở CP4 14:30 Thứ Bảy 28/11. Chấm ở rubric R6.
> Số lấy từ lượt `simulate-1@20261127-201002` (`cost/simulate-1.csv`, `cost/simulate-1-summary.md`, `traces/simulate-1.jsonl`). Lúc build dùng gói miễn phí vẫn tính theo giá gói trả phí.

## 1. Đầu vào

**Persona** (`cost/personas.yaml`; tỉ lệ và tần suất đều *(tự ước tính)*, chưa có phỏng vấn):

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

**Tỉ lệ đạt dùng để tính:** 20/21 (95,2%), lượt `run-2@20261127-191050`. Tỉ lệ này đo trên `gemini-3.5-flash-lite`; dùng cho `gemini-3.8-flash` là **giả định**, chưa đo. Nếu chấm chặt hơn (17/21), chi phí / task thành công của flash-lite là khoảng $0,0021.
**Đo token trên** `gemini-3.5-flash-lite`, **tính giá** cả hai model. Hai model tách token giống nhau hay không: chưa kiểm.

## 2. Kết quả mô phỏng

50 phiên, 88 lượt hỏi, seed 42, 166 lần gọi model, 0 phiên lỗi; token vào 117.315, ra 20.714.

| Persona | Số phiên | Token vào / phiên | Token ra / phiên | Gọi model / phiên | Chi phí / phiên flash-lite | 3.8-flash |
|---|---:|---:|---:|---:|---:|---:|
| `xem_cuoi_thang` | 19 | 1.476 | 294 | 2,0 | $0,0012 | $0,0044 |
| `theo_doi_hang_tuan` | 24 | 2.363 | 336 | 3,6 | $0,0016 | $0,0061 |
| `so_sanh_nhieu_thang` | 7 | 4.650 | 1.007 | 6,0 | $0,0039 | $0,0145 |

| Model | Chi phí / phiên | Chi phí / task thành công | / tháng — thấp | / tháng — cơ sở | / tháng — cao | / người / tháng (cơ sở) |
|---|---:|---:|---:|---:|---:|---:|
| `gemini-3.5-flash-lite` | $0,0017 | **$0,0018** | $16,95 | **$169,55** | $1.695,50 | $0,0057 |
| `gemini-3.8-flash` | $0,0066 | **$0,0070** | $64,73 | **$647,33** | $6.473,29 | $0,0216 |

Công thức:

- chi phí / phiên = (token vào × giá vào + token ra × giá ra) ÷ 1.000.000
- chi phí / task thành công = chi phí trung bình mỗi phiên ÷ tỉ lệ đạt — **không coi như đạt 100%**
- chi phí / tháng = Σ persona (người dùng × tỉ lệ × phiên / tháng × chi phí / phiên của persona)

## 3. So với impact

Impact (`spec.md` §2, *tự ước tính*): 2.200 người gặp pain × 20 phút = **44.000 phút / tháng** ở kịch bản cơ sở.

| Model | Chi phí / tháng (cơ sở) | Chi phí cho mỗi phút tiết kiệm | Quy ra mỗi giờ |
|---|---:|---:|---:|
| `gemini-3.5-flash-lite` | $169,55 | $0,0039 | $0,23 |
| `gemini-3.8-flash` | $647,33 | $0,0147 | $0,88 |

- Phép chia tính **toàn bộ** chi phí của 30.000 người dùng cho phần thời gian của 2.200 người gặp pain, nên nghiêng về phía bất lợi cho sản phẩm.
- Hai giả định chưa khớp nhau: impact lấy 2 lần / người / tháng, còn persona trung bình 3,2 phiên / người / tháng. Cả hai đều *(tự ước tính)*, cần phỏng vấn để chốt một số.
- Impact giả định bản chạy thử tiết kiệm trọn 10 phút mỗi lần (trần trên). Với 16.000 phút (mức thấp ở §2), flash-lite thành $0,0106 mỗi phút.
- Chưa quy ra đồng: không có nguồn cho giá trị một phút và tỷ giá.
- **Kết luận một dòng:** về chi phí model thì đáng làm **nếu** một phút của người dùng đáng hơn $0,004 (flash-lite) và impact ước tính đúng; chưa đủ để quyết Go vì pain chưa được phỏng vấn kiểm chứng.

## 4. Độ nhạy và ngoài phạm vi mô phỏng

Tách theo loại lời gọi trong `traces/simulate-1.jsonl`:

| Lời gọi | Số lần | Token vào | Token ra | Phần chi phí (flash-lite) |
|---|---:|---:|---:|---:|
| Hiểu câu hỏi (lần 1) | 88 | 69.556 | 4.867 | 38% |
| Gán nhóm (lần 2) | 78 | 47.759 | 15.847 | 62% |

| Cần gạt | flash-lite: / phiên · / tháng cơ sở | 3.8-flash: / phiên · / tháng cơ sở | Ghi chú |
|---|---|---|---|
| Như hiện tại | $0,0017 · $169,55 | $0,0066 · $647,33 | |
| Lưu nhãn đã gán (**chưa làm**), trần tiết kiệm: bỏ hết lời gọi gán nhóm | $0,0007 · $66,08 | $0,0028 · $281,46 | Thực tế cao hơn vì mô tả mới vẫn phải gán; cũng giúp nhãn ổn định |
| Đổi sang model mạnh hơn | — | cột này | Chi phí khoảng 3,8 lần; chất lượng chưa đo |
| Tỉ lệ đạt 17/21 thay vì 20/21 | task thành công ≈ $0,0021 | ≈ $0,0082 | Theo cách chấm chặt hơn |

- Số người dùng × 10 thì chi phí và impact cùng × 10, nên chi phí mỗi phút tiết kiệm không đổi.
- Nhiều giao dịch hơn: phần gán nhóm tăng theo số **kiểu mô tả**, không theo số giao dịch. Chưa đo.
- Chi phí ngoài model (hosting, lưu trữ, kết nối dữ liệu ngân hàng, giờ người xử lý khiếu nại): chưa tính.
