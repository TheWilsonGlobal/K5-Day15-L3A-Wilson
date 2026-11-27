# Báo cáo đánh giá — lượt 1 → một cải tiến → lượt 2

> Guide bước 4.1. Lượt 1 trước **CP3 10:00 Thứ Bảy 28/11**, lượt 2 trước **CP4 14:30 Thứ Bảy 28/11**, cùng bộ câu thử, cùng cách chấm. Chấm ở rubric R5.
> **Đã chạy lượt 1 và lượt 2** (27/11/2026, cùng bộ 21 câu, cùng model, cùng `grade.py` và `oracle.json`). Lượt 1 chạy code tại commit `1e37075`; lượt 2 chạy code sau cải tiến ở mục 3, commit cùng `eval/run-2.csv`.
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
| 2 | `run-2@20261127-191050` | **20/21** | **95,2%** | 3/4 | 11/11 | 6/6 | 0 | **Đạt** |

Theo metric (`eval/grade.py` in ra):

| Metric | Ngưỡng | Lượt 1 | Lượt 2 |
|---|---|---|---|
| `so_khop_cong_cu` | 100% | 21/21 (100%) đạt | 21/21 (100%) đạt |
| `dung_dap_an` | theo câu | 10/15 | 14/15 |
| `tu_choi_dung` | 100% câu `tu_choi` | 6/6 (100%) đạt | 6/6 (100%) đạt |
| `dung_ke_hoach` | ≥ 85% | 11/13 (84,6%) chưa đạt | 13/13 (100%) đạt |
| `khong_doan_bua` | ≥ 90% | 6/12 (50%) chưa đạt | 12/12 (100%) đạt |

Model cả hai lượt: `gemini-3.5-flash-lite` · 0 lỗi kỹ thuật. Lượt 1: 31 lần gọi model, token vào 20.975, ra 3.004. Lượt 2: 33 lần gọi, vào 24.209, ra 3.429 (C07 và C17 giờ đi hết luồng).

`grade.py` chấm trước, người rà (Phạm Ngọc Sơn, 27/11/2026) xác nhận cả 21 dòng của mỗi lượt trên bảng tóm tắt, không đổi `pass`.

**Đọc con số 20/21 cùng độ nhạy** (chấm theo đúng `pass_criterion` đã chốt ở CP2 là 20/21):

| Cách chấm lượt 2 | Câu qua | §7 (≥ 80%) |
|---|---|---|
| Theo `pass_criterion` đã chốt (**số chính thức**) | 20/21 = 95,2% | Đạt |
| Chặt hơn: đánh trượt thêm C07, C11, C17 vì bảng theo nhóm sai | 17/21 = 81,0% | Vẫn đạt |
| Chặt nhất: đánh trượt thêm cả C12 vì câu chữ sai về thời gian | 16/21 = 76,2% | **Không đạt** |

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

- Nhắm vào nhóm lỗi: **A** là chính (4/7 câu trượt) — đau nhất với người dùng vì con số sai vẫn khớp công cụ nên trông đáng tin: hai lần hỏi cùng một tháng ra hai số "Không rõ" khác nhau. Nhóm B, C và lỗi RV-01 sửa cùng đợt.
- Đã sửa gì (quy tắc tổng quát, không so khớp câu thử):

| Nhóm | Sửa | File |
|---|---|---|
| A | Mô tả chỉ có chữ thanh toán / hoá đơn và mã số → "Không rõ" bằng code, không gửi model | `codebase/tools.py` (`is_bare_bill_code`) |
| B | Prompt kế hoạch: hỏi về tiền đã hoàn là hỏi chi tiêu; xếp nhóm nhiều khoản trong một kỳ là `tong_chi`; `giao_dich` chỉ khi nhờ thực hiện | `codebase/agent.py` (`SYSTEM_PLAN`) |
| C | Tìm nơi bán thử thêm tên đã bỏ "quán", "tiệm", "cửa hàng", "nhà hàng", "shop" ở đầu | `codebase/tools.py` (`find_merchant`) |
| RV-01 | Lời gọi gán nhóm lỗi hoặc bị chặn → vẫn trả lời, để "Không rõ", ghi cảnh báo | `codebase/agent.py` (`_labels`) |

- **RV-01 chỉ kiểm bằng unit test** (`codebase/test_fixes.py`): lượt 2 và lượt mô phỏng không lần nào lời gọi gán nhóm bị lỗi.
- Kết quả: nhóm A **0/4 → 4/4** câu qua (nhóm B 0/2 → 2/2, C 0/1 → 1/1) · tổng **14/21 (66,7%) → 20/21 (95,2%)**. Trượt → qua: C05, C07, C11, C14, C17, C25, C30.
- **Nhóm A giảm, chưa hết:** mô tả `THANH TOAN HD 778120` đã ổn định, nhưng việc gán nhóm các mô tả khác vẫn đổi giữa các lần gọi (xem dưới).
- Câu nào **tệ đi** sau khi sửa:

| Câu | Lượt 1 → 2 | Hiện tượng (từ `eval/run-2.csv`) |
|---|---|---|
| **C01** | **qua → trượt** | `NHA SACH TRI THUC` bị gán Mua sắm thay vì Học tập: Mua sắm 22.059.000đ (11 giao dịch), đúng 21.788.000đ (10); Học tập 1.275.000đ (2), đúng 1.546.000đ (3). Ở lượt 1 mô tả này được gán đúng trong C01 |
| C07, C11, C17 | trượt → qua | Cùng lỗi `NHA SACH TRI THUC` (tháng 11 lệch 117.000đ ở C07, C17; tháng 10 lệch 271.000đ ở C11). Vẫn qua vì `pass_criterion` chỉ đòi dòng tổng. C30, cùng tháng 11, lại gán đúng |
| C12 | qua → qua | Mở đầu "Bạn không nói thời gian nên mình lấy tháng này" dù câu hỏi có "tháng này". Số đúng |

Chưa xác định được việc bỏ một mô tả khỏi lô gửi model (sửa nhóm A) có góp phần làm `NHA SACH TRI THUC` bị gán sai hay không.

## 4. Còn lại

| Lỗi chưa sửa | Nguy hiểm thế nào |
|---|---|
| Nhãn do model gán không ổn định giữa các lần gọi | **Cao nhất:** số theo nhóm sai nhưng khớp công cụ, trông đáng tin; bộ chấm không bắt ở C07, C11, C17 |
| Bộ chấm không đối chiếu số từng nhóm ở C07, C11, C17 | Điểm cao hơn chất lượng thật của bảng theo nhóm |
| Không tìm giao dịch theo số tiền (C16) | Người hỏi phải tự dò trong bảng |
| Dòng giả định thời gian hiện sai (C12) | Người hỏi nghĩ hệ thống không hiểu câu hỏi |
| Bộ lọc mô tả cài lệnh dựa trên danh sách từ | Có thể bị lách và làm lệch nhãn mục khác |
| Chưa đo lại: "theo từng nhóm" bị hiểu là nhóm "Không rõ"; hỏi một hãng xe bị tính cả nhóm Đi lại (`spec.md` §9) | Trả lời đúng số cho sai câu hỏi |

- **Nếu có thêm 1 tuần:** (1) lưu nhãn theo mô tả và dùng lại nhãn người dùng đã sửa, để một mô tả luôn ra một nhóm và bớt lời gọi (`cost/cost-estimate.md` §4); (2) thêm câu thử kiểm số từng nhóm và đo mỗi câu nhiều lần; (3) tìm giao dịch theo số tiền, sửa dòng giả định thời gian; (4) phỏng vấn và cho người ngoài nhóm dùng thử.
