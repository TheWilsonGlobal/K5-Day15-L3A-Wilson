# Dàn slide → lấy số từ file nào

> Guide bước 5.1. Luật: **không có bằng chứng thì không có slide**.
> Nguồn slide: `slides/demo-slides.html`. Bản nộp: `demo-slides.pdf` ở thư mục gốc, nộp tại CP4 14:30 Thứ Bảy 28/11. Kịch bản nói: `slides/demo-script.md`.

| # | Trang | Số lấy từ | Trạng thái |
|---|---|---|---|
| 1 | Người dùng & pain | `evidence/summary.md` | Chờ x/n, x/N, trích dẫn |
| 2 | Vì sao chọn bài này | `spec.md` §2 | Chờ p, f, t và lý do loại |
| 3 | Giải pháp | `spec.md` §4 | Xong |
| 4 | Demo live | `eval/benchmark.csv` | Xong |
| 5 | Đánh giá thế nào | `eval/README.md`, `eval/report.md` | Chờ lượt 1, 2 và cập nhật số câu |
| 6 | Chi phí khi dùng thật | `cost/cost-estimate.md` | Chờ mô phỏng chính thức |
| 7 | Kết luận | trang 1, 5, 6 | Chờ quyết định |
| 8 | Nếu có thêm 1 tuần | `eval/report.md` mục 4 · `validation/log.md` | Bản nháp theo lỗi thấy khi chạy thử; cập nhật sau lượt 2 |

Chỗ tô vàng `[CHỜ …]` phải thay hết trước khi nộp. Kiểm: tìm chữ `CHỜ` trong `demo-slides.html`.

## Xuất PDF (Windows PowerShell, đứng ở gốc repo)

```powershell
$edge = "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
$url  = ([Uri](Resolve-Path slides\demo-slides.html).Path).AbsoluteUri
Start-Process $edge -Wait -ArgumentList @('--headless','--disable-gpu','--no-pdf-header-footer',
  "--user-data-dir=`"$env:TEMP\slides-pdf`"", "--print-to-pdf=`"$PWD\demo-slides.pdf`"", $url)
```

Mở `demo-slides.pdf`: đúng 8 trang, không trang nào tràn.

**Trước khi lên:** tải repo về thư mục mới, chạy theo "Chạy trong 3 phút" của `README.md` · máy demo có `.env`, đã gọi thử trong 1 giờ · video dự phòng mở được bằng cửa sổ ẩn danh.

| Trang | Người nói |
|---|---|
| 1–2 | [CHỜ DỮ LIỆU THẬT: TV3] |
| 3–4 | Phạm Ngọc Sơn |
| 5 | [CHỜ DỮ LIỆU THẬT: TV2] |
| 6–8 | [CHỜ DỮ LIỆU THẬT: TV4] |
