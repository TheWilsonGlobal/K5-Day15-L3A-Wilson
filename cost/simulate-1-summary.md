# Tóm tắt mô phỏng simulate-1@20261127-201002

Do `python run.py simulate` sinh ra — không sửa tay. Chép bảng sang `cost/cost-estimate.md`.

| Persona | Số phiên mô phỏng | Lượt hỏi / phiên | Token vào / phiên | Token ra / phiên | Gọi model / phiên | Gọi công cụ / phiên |
|---|---:|---:|---:|---:|---:|---:|
| xem_cuoi_thang | 19 | 1 | 1476 | 294 | 2.0 | 5.0 |
| theo_doi_hang_tuan | 24 | 2 | 2363 | 336 | 3.6 | 9.6 |
| so_sanh_nhieu_thang | 7 | 3 | 4650 | 1007 | 6.0 | 21.4 |

Tỉ lệ đạt dùng để tính: 20/21 (95%) — lượt run-2@20261127-191050

- Tỉ lệ đạt lấy từ lượt nhóm chọn: eval/run-2.csv (--rate-from).

| Model (giá) | Chi phí / phiên | Chi phí / task thành công | Chi phí / câu hỏi đạt | Chi phí / tháng — thấp (3.000 người) | Chi phí / tháng — cơ sở (30.000 người) | Chi phí / tháng — cao (300.000 người) | Chi phí / người / tháng (cơ sở) |
|---|---:|---:|---:|---:|---:|---:|---:|
| gemini-3.5-flash-lite (vào 0.3 · ra 2.5 $/1M) | $0.0017 | $0.0018 | $0.0010 | $16.95 | $169.55 | $1,695.50 | $0.0057 |
| gemini-3.8-flash (vào 1.5 · ra 7.5 $/1M) | $0.0066 | $0.0070 | $0.0040 | $64.73 | $647.33 | $6,473.29 | $0.0216 |

- Chi phí / task thành công = chi phí / phiên ÷ tỉ lệ đạt. Chi phí / câu hỏi đạt = chi phí / phiên ÷ số lượt hỏi trung bình mỗi phiên (1.8) ÷ tỉ lệ đạt — tỉ lệ đạt đo theo từng câu thử.
- Token đo trên model: gemini-3.5-flash-lite. Giá tính theo từng model trong bảng — model khác bộ tách token thì số token thật có thể lệch; ghi rõ "đo trên model X, tính giá model Y" trong cost/cost-estimate.md.
- Phiên lỗi (không tính vào trung bình): 0/50.
