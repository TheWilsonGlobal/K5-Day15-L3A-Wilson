# Báo cáo đánh giá — lượt 1 → một cải tiến → lượt 2

> Guide bước 4.1. Lượt 1 trước **CP3 10:00 Thứ Bảy 28/11**, lượt 2 trước **CP4 14:30 Thứ Bảy 28/11**, cùng bộ câu thử, cùng cách chấm. Chấm ở rubric R5.
> **Chưa chạy lượt chính thức nào.** Lượt 1 chạy sau khi bộ câu thử có ≥1/3 câu từ nguồn thật và đã đóng bộ.
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
| 1 | [CHỜ DỮ LIỆU THẬT] | | | | | | | |
| 2 | [CHỜ DỮ LIỆU THẬT] | | | | | | | |

Theo metric (`eval/grade.py` in ra):

| Metric | Ngưỡng | Lượt 1 | Lượt 2 |
|---|---|---|---|
| `so_khop_cong_cu` | 100% | [CHỜ DỮ LIỆU THẬT] | [CHỜ DỮ LIỆU THẬT] |
| `dung_dap_an` | theo câu | [CHỜ DỮ LIỆU THẬT] | [CHỜ DỮ LIỆU THẬT] |
| `tu_choi_dung` | 100% câu `tu_choi` | [CHỜ DỮ LIỆU THẬT] | [CHỜ DỮ LIỆU THẬT] |
| `dung_ke_hoach` | ≥ 85% | [CHỜ DỮ LIỆU THẬT] | [CHỜ DỮ LIỆU THẬT] |
| `khong_doan_bua` | ≥ 90% | [CHỜ DỮ LIỆU THẬT] | [CHỜ DỮ LIỆU THẬT] |

Kết quả từng câu: `eval/run-1.csv`, `eval/run-2.csv`. Trace: `traces/run-1.jsonl`, `traces/run-2.jsonl`.

## 2. Lỗi lượt 1 — gom thành nhóm có tên

| Nhóm lỗi | Số câu | Câu |
|---|---|---|
| [CHỜ DỮ LIỆU THẬT] | | |

**≥3 lỗi cụ thể** (chép nguyên từ `eval/run-1.csv`):

| Câu | Input | Output | Vì sao sai |
|---|---|---|---|
| [CHỜ DỮ LIỆU THẬT] | | | |
| [CHỜ DỮ LIỆU THẬT] | | | |
| [CHỜ DỮ LIỆU THẬT] | | | |

## 3. Một lần cải tiến

- Nhắm vào nhóm lỗi: [CHỜ DỮ LIỆU THẬT] — vì sao là nhóm **đau nhất với người dùng**: [CHỜ DỮ LIỆU THẬT]
- Đã sửa gì (có thể vài thay đổi cùng nhắm nhóm lỗi đó): [CHỜ DỮ LIỆU THẬT]
- Kết quả: nhóm lỗi đó [CHỜ DỮ LIỆU THẬT: x/y → x/y] · tổng [CHỜ DỮ LIỆU THẬT: % → %]
- Câu nào **tệ đi** sau khi sửa: [CHỜ DỮ LIỆU THẬT]

## 4. Còn lại

- Lỗi chưa sửa + nguy hiểm thế nào: [CHỜ DỮ LIỆU THẬT]
- Nếu có thêm 1 tuần: [CHỜ DỮ LIỆU THẬT]
