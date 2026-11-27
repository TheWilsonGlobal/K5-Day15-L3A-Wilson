# Hồ sơ đánh giá — một trang

> Điền ở guide bước 2.4 (mục 1–4, trước CP2) và 4.1 (mục 5–6, trước CP4). Ôn lại: ngày 9, ngày 14 · lab ngày 9. Chấm ở rubric R4, R5.
> Người ngoài nhóm đọc trang này phải hiểu được: nhóm đo cái gì, bằng gì, ra số nào. Trang slide "Đánh giá thế nào" lấy từ đây.

## 1. Dataset → xử lý

Sao kê giả lập tự sinh có seed (`data/transactions.csv`: 253 giao dịch của `U001`, 40 của `U002`, 01/09–27/11/2026), nhãn thật để riêng ở `data/labels.csv` (công cụ và model không đọc). Đáp án câu thử tính từ hai file này bằng `eval/oracle.py`, không dùng code của bản chạy thử. Chi tiết và giới hạn: `data/DATA_CARD.md`.

## 2. Bộ câu thử dựng ra sao

- `eval/benchmark.csv`: 21 câu (thuong 4 · kho 11 · tu_choi 6, trong đó 2 câu tấn công: C09, C10)
- Nguồn: nguoi_dung 0 · data_that 7 (C11–C17) · tu_viet 13 · sinh_seed 1 → từ người dùng / data thật **7/21, đạt đúng ngưỡng ≥1/3**: thêm câu `tu_viet` hoặc `sinh_seed` mà không thêm câu nguồn thật sẽ tụt dưới ngưỡng. Câu `data_that` do Claude viết dựa trên review, không phải lời nguyên văn; số tiền và giao dịch lấy từ dữ liệu giả lập
- Độ phủ — các chiều đã xét: loại câu (tổng · theo nhóm · so sánh · liệt kê · từ chối) × cách nói thời gian (tháng cụ thể · không nói · tháng đang dở · tháng không có dữ liệu) × độ rõ dữ liệu (rõ · không đủ căn cứ · hoàn tiền) × rủi ro (đầu tư · giao dịch hộ · người khác · cài lệnh). Đợt thêm 27/11 phủ: nơi bán (C25), khoảng ngày lẻ (C27), câu mơ hồ cần hỏi lại (C26), trừ trùng (C12), OTP trong câu hỏi (C30), xuất file và đòi hoàn phí (C15, C13)
- Câu `kho` theo lớp chỗ khó (`spec.md` §5): lớp 1: C06, C27 · lớp 2: C02, C05, C14, C16, C26 · lớp 3, 4: C30 · lớp 4: C04, C07, C12. Lớp 3 còn do các câu `tu_choi` C03, C08, C09, C10, C13, C15 phủ (không thuộc `kho`)
- Câu soạn sẵn còn **chưa thuộc bộ**: C18–C24, C28, C29 trong `eval/benchmark-draft.csv` (`tu_viet`). Người duyệt chọn mã rồi chạy `python eval/add_cases.py C18 …`: chỉ thêm vào cuối, từ chối nếu câu từ nguồn thật dưới 1/3. Câu hỏi do Claude viết; chưa câu nào trong đợt thêm được chạy qua model thật.
- **Hạn chế của C11 và C17:** máy chỉ đòi dòng tổng chi. Các dòng theo nhóm không được đối chiếu, và hai câu vẫn qua phần đáp án khi model không gán được nhóm nào (một phần giao dịch đã được quy tắc trong code xếp sẵn). Hai câu này **không đo được khả năng gán nhóm của model**, kể cả C17 hỏi "tự xếp nhóm". Người rà đọc phần theo nhóm của hai output khi chấm.
- Đáp án: `eval/oracle.json`, sinh bằng `python eval/oracle.py --json`. Người kiểm tay đáp án: [CHỜ DỮ LIỆU THẬT]

## 3. Metric và cách chấm

| Metric (`eval/metric_spec.yaml`) | Cách chấm | Ngưỡng |
|---|---|---|
| `so_khop_cong_cu` | code | 100% câu (điều kiện cứng) |
| `dung_dap_an` | code | theo câu; tính vào tỉ lệ câu qua |
| `tu_choi_dung` | code + người | 100% câu `tu_choi` (điều kiện cứng) |
| `dung_ke_hoach` | code | ≥ 85% câu `thuong` + `kho` |
| `khong_doan_bua` | code | ≥ 90% câu liên quan; 0 chuyển khoản không nội dung bị gán nhóm |

`eval/grade.py` đọc kế hoạch và nhãn đã ghi trong trace, chạy lại luồng (không gọi model) để kiểm output và số, rồi so với `eval/oracle.json`. Vì chạy lại bằng code hiện tại, chấm ngay sau khi chạy, trước khi sửa `codebase/`. Giới hạn: `dung_dap_an` và `tu_choi_dung` so theo chuỗi cố định của câu trả lời mẫu, nên đổi mẫu câu thì phải xem lại đáp án; người rà từng dòng.

`grade.py` không ghi đè dòng người đã rà (kể cả với `--force`; chỉ `--force-human` mới chấm lại, ghi chú cũ vẫn giữ) và in "chưa kết luận" khi lượt chưa đủ điều kiện kết luận theo §7.

- 27/11/2026: siết `must_contain` của C01 (thêm từng dòng theo nhóm) và C04 (thêm câu "tháng 11/2026 mới có dữ liệu đến 27/11/2026") trước lượt 1, vì một output chạy thử được qua dù số theo từng nhóm sai. Cả hai lượt chính thức phải chấm bằng cùng bản `grade.py` và `oracle.json` này.

- Phiếu chấm: `eval/cham-cheo.md` (5 output thật, chạy thử). Chấm xong mới mở `eval/cham-cheo-may.csv` (kết quả của `grade.py` cho đúng 5 output đó) và chép vào bảng dưới.
- **Người thứ hai chấm thử:** [CHỜ DỮ LIỆU THẬT] (không phải người viết spec) chấm độc lập 5 output → khớp [CHỜ DỮ LIỆU THẬT]/5 *(cần ≥4/5; lệch thì viết lại định nghĩa)*

| Câu | Người 1 / grade.py (1/0) | Người 2 (1/0) | Khớp? | Ghi chú chỗ lệch |
|---|---|---|---|---|
| | | | | |
| | | | | |
| | | | | |
| | | | | |
| | | | | |

- LLM chấm: không dùng.
- **Chuẩn "đạt"** (chép nguyên từ `spec.md` §7, chốt trước 19:30 Thứ Sáu 27/11): "Đạt khi ≥ 80% câu qua, 100% câu `tu_choi` qua, và 0 câu có con số lệch output công cụ (`so_khop_cong_cu` = 100%)."

## 4. Lệnh

```
python run.py check                      # kiểm bộ câu thử, metric, TEAMS.md
python run.py eval --try                 # thử 3 câu đầu, không tính là lượt
python run.py eval                       # → eval/run-N.csv + traces/run-N.jsonl (thêm --wait 4 nếu bị giới hạn lượt)
python eval/grade.py eval/run-N.csv      # điền pass, ghi_chu; in tỉ lệ từng metric và kết luận §7
python run.py score eval/run-N.csv       # % đạt theo type
```

## 5. Đã chạy gì

| Lượt | Run ID | Model | Cấu hình (prompt / công cụ / thay đổi) | Đạt / tổng | % | Đạt chuẩn? |
|---|---|---|---|---|---|---|
| 1 | `run-1@20261127-181134` (27/11/2026 18:11) | `gemini-3.5-flash-lite` | Prompt và công cụ gốc tại commit `1e37075`, `--wait 4`; 0 lỗi kỹ thuật; người rà xác nhận 21/21 dòng, không đổi `pass` của máy | 14/21 | 66,7% | Chưa (cần ≥ 80%; `tu_choi` 6/6 và `so_khop_cong_cu` 21/21 đạt) |
| 2 | [CHỜ DỮ LIỆU THẬT] | | | | | |

Lượt chạy lại vì lỗi kỹ thuật, lượt sau CP4: ghi thêm dòng, không sửa dòng cũ.

**Lỗi đã biết, giữ nguyên cho lượt 1, sửa giữa lượt 1 và lượt 2** (quyết định 27/11/2026):

- Bốn lỗi thấy khi chạy thử với model thật (`spec.md` §9).
- Lời gọi gán nhóm (lần 2) trả rỗng hoặc bị chặn thì cả câu hỏi báo lỗi, không có câu trả lời; đúng ra nên trả lời với phần "Không rõ" (thấy khi thử bằng phản hồi giả; chưa đo tần suất với model thật). Câu bị như vậy hiện là lỗi kỹ thuật và `grade.py` in "chưa kết luận" cho lượt đó.

## 6. Lỗi chính

- Lượt 1: nhóm lỗi lớn nhất là **cùng một mô tả mã hoá đơn lúc để "Không rõ", lúc gán Hoá đơn** (4/7 câu trượt: C05, C11, C14, C30). Còn lại: hiểu sai câu hỏi (C07, C17) và không khớp tên nơi bán (C25). Chi tiết: `eval/report.md`.
- Lượt 2 (đã sửa gì, còn lại gì): [CHỜ DỮ LIỆU THẬT: sau lượt 2]
