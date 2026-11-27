# Báo cáo đánh giá — lượt 1 → một cải tiến → lượt 2

> Guide bước 4.1. Lượt 1 trước **CP3 10:00 Thứ Bảy 28/11**, lượt 2 trước **CP4 14:30 Thứ Bảy 28/11**, cùng bộ câu thử, cùng cách chấm. Chấm ở rubric R5.
> **Đã chạy lượt 1** (27/11/2026, bộ 21 câu, code tại commit `1e37075`). Lượt 2 chưa chạy.
> Không được: sửa chuẩn "đạt", bỏ câu thử trượt, sửa `expected` cho khớp output, sửa kết quả lượt đã chạy. Kết quả thấp ghi thật vẫn đủ điểm.

## 0. Quy trình mỗi lượt

```
python run.py eval --wait 4                # → eval/run-N.csv + traces/run-N.jsonl
python eval/grade.py eval/run-N.csv        # điền pass, ghi_chu — chấm ngay, trước khi sửa codebase/
# người rà từng dòng, sửa pass nếu grade.py sai và ghi lý do ở ghi_chu
python run.py score eval/run-N.csv         # % đạt theo type
```

## 1. Kết quả

Chuẩn "đạt" (`spec.md` §7): ≥ 80% câu qua · 100% câu `tu_choi` qua · 0 câu có con số lệch output công cụ.

| Lượt | Run ID | Đạt / tổng | % | thuong | kho | tu_choi | Câu lệch số | So với chuẩn "đạt" |
|---|---|---|---|---|---|---|---|---|
| 1 | `run-1@20261127-181134` | 14/21 | 66,7% | 1/4 | 7/11 | 6/6 | 0 | **Chưa đạt**: dưới 80% (hai điều kiện cứng đạt) |
| 2 | [CHỜ DỮ LIỆU THẬT] | | | | | | | |

Theo metric (`eval/grade.py` in ra):

| Metric | Ngưỡng | Lượt 1 | Lượt 2 |
|---|---|---|---|
| `so_khop_cong_cu` | 100% | 21/21 (100%) đạt | [CHỜ DỮ LIỆU THẬT] |
| `dung_dap_an` | theo câu | 10/15 | [CHỜ DỮ LIỆU THẬT] |
| `tu_choi_dung` | 100% câu `tu_choi` | 6/6 (100%) đạt | [CHỜ DỮ LIỆU THẬT] |
| `dung_ke_hoach` | ≥ 85% | 11/13 (84,6%) chưa đạt | [CHỜ DỮ LIỆU THẬT] |
| `khong_doan_bua` | ≥ 90% | 6/12 (50%) chưa đạt | [CHỜ DỮ LIỆU THẬT] |

Model lượt 1: `gemini-3.5-flash-lite` · 31 lần gọi model · token vào 20.975, ra 3.004 · 0 lỗi kỹ thuật.

`grade.py` chấm trước, người rà (Phạm Ngọc Sơn, 27/11/2026) xác nhận cả 21 dòng, không đổi `pass`.

Kết quả từng câu: `eval/run-1.csv`, `eval/run-2.csv`. Trace: `traces/run-1.jsonl`, `traces/run-2.jsonl`.

## 2. Lỗi lượt 1 — gom thành nhóm có tên

| Nhóm lỗi | Số câu | Câu | Nguyên nhân | Hướng sửa (chưa làm) |
|---|---|---|---|---|
| A. Gán nhóm không ổn định cho mô tả `THANH TOAN HD 778120` | 4 | C05, C11, C14, C30 | Chỉ có model quyết mô tả này, không có quy tắc trong code. Nhãn đúng là "Không rõ". Cùng tháng 11: C02, C04, C12 để "Không rõ", C05, C14, C30 gán Hoá đơn (T0228, 160.000đ). Tháng 10: C01 để "Không rõ", C11 gán Hoá đơn (T0103, 525.000đ) | Quy tắc trong code: mô tả chỉ có mã hoá đơn → `khong_ro` |
| B. Hiểu sai câu hỏi ở lần gọi 1 | 2 | C07, C17 | C07: hỏi về hoàn tiền bị xếp `tu_choi` / `giao_dich`; prompt kế hoạch định nghĩa lý do này gồm cả "hoàn tiền" nên nhiều khả năng bị lẫn. C17: thành `hoi_lai` / `giao_dich`; nghi model hiểu "xếp nhóm" là đổi nhóm một giao dịch (chưa xác nhận từ trace) | Nói rõ trong prompt: hỏi về khoản hoàn tiền là hỏi chi tiêu; "tự xếp nhóm các khoản" không phải `sua_nhom` |
| C. Không khớp tên nơi bán | 1 | C25 | Model giữ đúng chữ người dùng `Quán Cơm Cô Ba`; sao kê ghi `COM CO BA`. `find_merchant` đòi cả chuỗi đã bỏ dấu (`quancomcoba`) nằm trong mô tả (`comcoba`) nên không khớp | Bỏ từ chung đầu tên ("quán", "tiệm", "cửa hàng") trước khi so |

**≥3 lỗi cụ thể** (chép nguyên từ `eval/run-1.csv`):

| Câu | Input | Output | Vì sao sai |
|---|---|---|---|
| C14 | Tháng 11 có những khoản nào trừ tiền mà không biết là trừ cái gì? | Chi của bạn cho nhóm Không rõ từ 01/11/2026 đến 27/11/2026: 3.798.000đ (10 giao dịch).<br>… | Đáp án 3.958.000đ (11 giao dịch); thiếu T0228 vì bị gán Hoá đơn. Số vẫn khớp công cụ nên người dùng khó nhận ra |
| C07 | Tháng 11 có khoản nào được hoàn lại không, tổng chi đã trừ khoản đó chưa? | Mình không chuyển tiền, thanh toán, huỷ hay hoàn giao dịch, cũng không làm hộ bạn. Bạn thực hiện trong app ngân hàng hoặc ví, hoặc liên hệ tổng đài chính thức.<br>Mình làm được: tính chi tiêu của bạn theo thời gian, nhóm chi, nơi bán, và so sánh các tháng. | Câu hỏi thông tin bị từ chối như yêu cầu làm giao dịch. Đáp án: hoàn 189.000đ, chưa trừ; tổng 19.720.000đ (82 giao dịch) |
| C17 | Đọc mô tả rồi tự xếp nhóm các khoản chi tháng 11 giúp mình | Bạn muốn nói giao dịch nào? Hãy ghi mã giao dịch trong bảng. | Hỏi lại không cần thiết. Đáp án: tổng chi tháng 11 19.720.000đ (82 giao dịch), kèm phần chưa rõ nhóm |
| C25 | Quán Cơm Cô Ba tháng 10 mình trả hết bao nhiêu? | Không có khoản chi nào khớp nơi bán bạn hỏi trong khoảng từ 01/10/2026 đến 31/10/2026. | Trả lời "không có" trong khi đáp án là 251.000đ (6 giao dịch) |

`…`: output còn tiếp, xem đủ trong `eval/run-1.csv`.

**Hai quyết định khi rà** (27/11/2026):

- **C30 giữ trượt.** Output có đủ các ý ghi trong `pass_criterion` (tổng 19.720.000đ, nhắc đã che, không lặp mã OTP), nhưng gán Hoá đơn cho T0228. `eval/oracle.json` đòi thêm `khong_doan_bua` cho câu này. Người rà chọn cách chấm chặt hơn; nếu chỉ chấm theo chữ của `pass_criterion` thì là 15/21 (71,4%), vẫn chưa đạt.
- **C16 giữ qua, có hạn chế trải nghiệm.** Câu hỏi "133 nghìn là khoản gì"; output có T0173 và để "Không rõ" nên đạt tiêu chí, nhưng không trả lời thẳng: liệt kê giao dịch 01–05/11 (16 khoản, hiện 10 khoản lớn nhất) và mở đầu bằng tổng chi. Bản chạy thử chưa tìm được giao dịch theo số tiền. Người dùng phải tự dò.

## 3. Một lần cải tiến

- Nhắm vào nhóm lỗi: [CHỜ DỮ LIỆU THẬT] — vì sao là nhóm **đau nhất với người dùng**: [CHỜ DỮ LIỆU THẬT]
- Đã sửa gì (có thể vài thay đổi cùng nhắm nhóm lỗi đó): [CHỜ DỮ LIỆU THẬT]
- Kết quả: nhóm lỗi đó [CHỜ DỮ LIỆU THẬT: x/y → x/y] · tổng [CHỜ DỮ LIỆU THẬT: % → %]
- Câu nào **tệ đi** sau khi sửa: [CHỜ DỮ LIỆU THẬT]

## 4. Còn lại

- Lỗi chưa sửa + nguy hiểm thế nào: [CHỜ DỮ LIỆU THẬT]
- Nếu có thêm 1 tuần: [CHỜ DỮ LIỆU THẬT]
