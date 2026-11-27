# AGENTS.md — hướng dẫn cho coding agent (Claude Code, Cursor, Codex…) làm việc trong repo này

> Nhóm Wilson · Track E · E1 giải thích chi tiêu từ sao kê (dữ liệu giả lập).

## Repo này là gì

Repo nộp bài hackathon AI20K của nhóm: một bản chạy thử AI cho **một lát cắt** (xem `spec.md` §4), kèm bằng chứng, bộ câu thử và mô phỏng chi phí. Mọi câu trả lời phải chạy được bằng các lệnh dưới đây.

## Lệnh

```
python run.py                    # chạy bản chạy thử
python run.py check              # kiểm eval/benchmark.csv + eval/metric_spec.yaml
python run.py eval --try         # thử 3 câu đầu
python run.py eval               # chạy cả bộ → eval/run-N.csv + traces/run-N.jsonl
python eval/grade.py eval/run-N.csv
python run.py score eval/run-N.csv
python -m unittest discover -s codebase -p "test_*.py"
python run.py simulate --try     # thử mô phỏng chi phí 10 phiên
python run.py simulate           # mô phỏng chi phí → cost/simulate-N.csv
```

Khung chỉ dùng thư viện chuẩn của Python. Thêm thư viện thì ghi vào `requirements.txt`.

## Cấu trúc code

| File | Ai sửa | Hợp đồng |
|---|---|---|
| `codebase/agent.py` | nhóm | `answer(text) -> {"output": str}` — luồng chính, đúng hình dạng ở `spec.md` §4 |
| `codebase/ai.py` | nhóm | `call_model(system, user) -> {"text", "model", "tokens_in", "tokens_out"}`, giữ `@model_call`. Token lấy từ `usage` của API, không ước lượng |
| `codebase/tools.py` | nhóm | mỗi công cụ một hàm có `@tool`, docstring: tên · input · output · có tác động ra ngoài không |
| `codebase/tracing.py`, `eval/run_eval.py`, `cost/simulate.py`, `run.py` | **khung — không sửa** | ghi trace, chạy bộ câu thử, mô phỏng chi phí |

## Luật — agent KHÔNG được làm

- Không commit `.env`, API key, dữ liệu cá nhân thật, nguyên file data BTC cấp.
- Không sửa `eval/run-*.csv`, `cost/simulate-*.csv`, `traces/*` đã chạy (trừ điền cột `pass`, `ghi_chu`).
- Không sửa chuẩn "đạt" (`spec.md` §7), `eval/metric_spec.yaml` sau CP2; không xoá câu thử trượt, không sửa `expected` cho khớp output.
- Không bịa người được phỏng vấn, trích dẫn, câu trả lời khảo sát, số liệu. Số không có nguồn thì ghi rõ *(tự ước tính)*.
- Công cụ có tác động ra ngoài (gửi tin, sửa dữ liệu, chấm điểm): chỉ tạo bản nháp chờ người duyệt.
- Không viết prompt "giấu" câu thử vào code (vd so khớp nguyên văn input của bộ câu thử).

## Quy ước của nhóm

- **Ngôn ngữ:** trả lời người dùng, tài liệu và chú thích bằng tiếng Việt; xưng "mình", gọi "bạn".
- **Code:** chỉ thư viện chuẩn Python; tên hàm tiếng Anh, giá trị miền tiếng Việt không dấu (`an_uong`, `tong_chi`); khoá `*_vnd` là tiền, `n_*` là số đếm, `*_pct` là phần trăm (`verify_numbers` dựa vào đây).
- **Duyệt:** agent không tự commit, không push, không tạo nhánh. Phạm Ngọc Sơn (đội trưởng) duyệt diff trước khi commit.
- **Trước khi đề nghị commit:** test đạt, `python run.py check` chạy được, `git ls-files .env` rỗng.

## Bất biến của bài toán — không được phá

- Model chỉ trả JSON gồm giá trị trong danh sách cho phép; không viết chữ cho người dùng, không tính toán.
- Mọi số tiền do `tools.py` tính; câu trả lời dựng từ mẫu và qua `verify_numbers`.
- Không công cụ nào nhận mã người dùng làm tham số; không có công cụ chuyển tiền hay giao dịch.
- Mô tả đáng ngờ không đi vào lời gọi gán nhóm chung.
- `codebase/` không đọc `data/labels.csv`; `eval/oracle.py` không import `tools.py` hay `agent.py`.
- Đáp án: không nói thời gian → tháng hiện tại và nói rõ · hoàn tiền không trừ vào tổng chi · tháng đang dở so cùng kỳ.
- Prompt và code không chứa nguyên văn input của câu thử.

## Bí mật và dữ liệu

- Không đọc, in, log hay dán giá trị trong `.env`; `.env.example` chỉ có tên biến, giá trị trống.
- Key đi trong header, không trong URL; thông báo lỗi phải xoá key trước khi ném ra (lỗi được ghi vào file sẽ commit).
- Chỉ dùng dữ liệu giả lập: không đưa sao kê thật, tên, số điện thoại, số tài khoản thật vào repo hay vào model.
- Test không gọi mạng (`MODEL_PROVIDER=fake`).
