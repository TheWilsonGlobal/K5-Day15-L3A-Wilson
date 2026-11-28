# Reflection — Phạm Ngọc Sơn

## 1. Vai trò + phần mình làm (trỏ tới file / commit)

Mình là Đội trưởng nhóm Wilson (Lớp L3A, Phòng H210, Zone 1), phụ trách thiết kế kiến trúc workflow cố định cho Track E1, nối model thật (`gemini-3.5-flash-lite`, `groq`) trong `codebase/ai.py`, `codebase/agent.py`, `codebase/tools.py`, kiểm soát chất lượng/bảo mật và điều phối nộp 4 mốc CP1–CP4 (`15/15đ`). Các mốc chính gồm: khởi tạo khung repo & nháp CP1 (`0a8609b`, `379ebdb`), nối model thật + bộ chấm `eval/grade.py` + `eval/oracle.py` (`25d4160`), duyệt tay 150/150 review & mở rộng 21 câu thử cho CP2 (`1e37075`), chạy Lượt 1 `14/21` (`1c90869`), cải tiến 3 nhóm lỗi giúp Lượt 2 đạt `20/21 (95,2%)` kèm mô phỏng 50 phiên & slide (`1bd5863`), và cập nhật link video dự phòng CP4 (`577fbe6`).

## 2. AI hỗ trợ mình thế nào (việc gì, công cụ gì, chỗ nào phải sửa lại output AI)

Mình dùng Claude Code và Antigravity để hỗ trợ lập kế hoạch, sinh dữ liệu giả lập có seed (`data/generate.py`), viết công cụ/test (`322` unit test), dựng khung báo cáo và slide HTML/PDF (`docs/ai-usage.md`). Tuy nhiên mình vẫn phải kiểm và chốt lại nhiều chỗ quan trọng: tách metric `so_khop_cong_cu` (100% điều kiện cứng) khỏi `dung_dap_an` để tránh model gán sai nhóm làm trượt nhầm điều kiện cứng, bổ sung bộ lọc tách mô tả nghi prompt injection khỏi batch gán nhãn, kiểm tay toàn bộ 150/150 review trong `evidence/reviews.csv` (sửa 2 nhãn ranh giới `14831017080` và `14272479886`), và đổi câu demo live ở slide 4 từ `C01` sang câu nơi bán `Quán Cơm Cô Ba` để tránh rủi ro model gán sai nhóm khi thuyết trình.

## 3. Một câu thử trượt của nhóm và mình học được gì từ nó

Ở Lượt 1, 4/7 câu trượt (`C05`, `C11`, `C14`, `C30`) đều bắt nguồn từ một mô tả duy nhất là `THANH TOAN HD 778120`: khi không có quy tắc trong code, model lúc xếp là `Không rõ`, lúc lại đoán thành `Hoá đơn` giữa các lần gọi khác nhau trong cùng một lượt, làm tổng tiền nhóm `Không rõ` bị lệch dù mọi phép cộng trong code vẫn khớp 100% (`so_khop_cong_cu = 21/21`). Bài học lớn nhất mình rút ra là trong sản phẩm tài chính, phần nào có quy tắc xác định được bằng code thì phải khóa bằng code (như mã hóa đơn trơ không rõ dịch vụ → ép `khong_ro`), và không thể chỉ kiểm "số khớp công cụ" mà phải kiểm độc lập cả phần phân loại đầu vào.
