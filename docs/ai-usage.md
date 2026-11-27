# Khai báo dùng AI

README có mục "Dùng AI vào việc gì" (bản tóm tắt). Chi tiết ở đây.

> Luật của đề: dùng AI để làm bài thoải mái, nhưng **ai không giải thích được phần có tên mình thì phần đó nhận 0 điểm**. Khai thiếu không bị trừ; giấu mới bị.

**Công cụ:** Claude Code (trợ lý viết code của Anthropic) để soạn · `gemini-3.5-flash-lite` là model trong bản chạy thử · Groq (một model Qwen) chỉ dùng gọi thử nhánh kết nối thứ hai.
Cập nhật lần cuối: Thứ Bảy 28/11/2026. Việc làm thêm sau đó: bổ sung dòng.

| Việc | Công cụ AI | AI làm gì | Người kiểm / sửa gì | Ai phụ trách |
|---|---|---|---|---|
| Kế hoạch thực thi | Claude Code | Đọc đề và rubric, soạn kế hoạch theo mốc | Đã duyệt kế hoạch và chốt quy ước đáp án; [CHỜ DỮ LIỆU THẬT: sửa gì thêm] | Phạm Ngọc Sơn |
| Code bản chạy thử (`codebase/`) | Claude Code | Viết công cụ, luồng, nối model, giao diện dòng lệnh, test; sau lượt 1 phân tích lỗi, viết 4 sửa đổi và test cho lượt 2 | [CHỜ DỮ LIỆU THẬT: đã đọc file nào, sửa gì] | [CHỜ DỮ LIỆU THẬT] |
| Prompt và thiết kế lời gọi model | Claude Code | Viết hai prompt, danh sách giá trị cho phép, bộ lọc mô tả đáng ngờ, bước kiểm số | [CHỜ DỮ LIỆU THẬT] | [CHỜ DỮ LIỆU THẬT] |
| Dữ liệu `synthetic` (`data/`) | Claude Code | Viết bộ sinh và nhãn thật, seed `20261127` | [CHỜ DỮ LIỆU THẬT: kiểm tay ≥30 dòng, khớp x/30] | [CHỜ DỮ LIỆU THẬT] |
| Câu thử (`eval/benchmark.csv`) | Claude Code | Soạn 10 câu đầu: 9 `tu_viet`, 1 `sinh_seed`; soạn thêm 20 câu nháp (7 dựa trên review, 13 `tu_viet`), script thêm câu và phiếu chấm chéo, phiếu kiểm dữ liệu, phiếu gắn nhãn thứ hai | Phạm Ngọc Sơn duyệt thêm 11 câu (C11–C17, C25–C27, C30) → 21 câu. [CHỜ DỮ LIỆU THẬT: kiểm tay đáp án] | Phạm Ngọc Sơn |
| Đáp án và bộ chấm | Claude Code | Viết `oracle.py`, `grade.py`, `metric_spec.yaml` theo phương án đã chốt | [CHỜ DỮ LIỆU THẬT: chấm chéo 5 output, khớp x/5] | [CHỜ DỮ LIỆU THẬT] |
| Chấm cột `pass` | Không dùng LLM chấm; Claude Code chạy `grade.py` và soạn bảng tóm tắt, ghi chú lỗi, đề xuất cách chấm | `grade.py` chấm bằng code | Lượt 1: xác nhận 21/21 dòng, đổi 0 (quyết C30 giữ trượt, C16 giữ qua). Lượt 2: xác nhận 21/21 dòng, đổi 0 (giữ 20/21 theo `pass_criterion`). Cả hai lượt rà trên bảng tóm tắt do Claude soạn, không phải chấm mù | Phạm Ngọc Sơn |
| Bằng chứng | Claude Code | Soạn giả thuyết nháp, cách lấy mẫu, kịch bản phỏng vấn, script đếm; viết script tải review công khai, tải 150 review, **gắn nhãn nháp**, gợi ý ở các dòng ranh giới và chép số vào tài liệu. **Không** tạo người, trích dẫn hay review | Kiểm 150/150 dòng trên đoạn trích (thấy sẵn nhãn nháp), khớp 148/150, đổi 2 nhãn, chốt quy tắc ranh giới. [CHỜ DỮ LIỆU THẬT: xác nhận giả thuyết viết trước khi hỏi; sửa gì trong kịch bản; người thứ hai x/10] | Phạm Ngọc Sơn |
| Tra nguồn công khai | Claude Code (tìm web) | Tìm trang sản phẩm tương tự và nguồn số người dùng | [CHỜ DỮ LIỆU THẬT: mở từng link, dùng thử sản phẩm] | [CHỜ DỮ LIỆU THẬT] |
| Chi phí | Claude Code | Soạn persona *(tự ước tính)*, chép giá từ bảng của BTC, chạy mô phỏng 50 phiên, tính độ nhạy và viết `cost-estimate.md` | [CHỜ DỮ LIỆU THẬT: người kiểm số, sửa persona theo phỏng vấn] | [CHỜ DỮ LIỆU THẬT] |
| Slide, kịch bản, tài liệu | Claude Code | Soạn `spec.md`, slide, kịch bản demo, khung báo cáo, README | [CHỜ DỮ LIỆU THẬT] | [CHỜ DỮ LIỆU THẬT] |
| Reflection | Không | Chỉ tạo khung và liệt kê commit; mỗi người tự viết | Tự viết | Từng người |

**Không dùng AI để:** tạo người được phỏng vấn, trích dẫn, câu trả lời khảo sát hay người dùng thử; sửa kết quả các lượt đã chạy (`eval/run-*.csv`, `cost/simulate-*.csv`, `traces/`).
