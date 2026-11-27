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
python eval/grade.py eval/run-N.csv                  # chấm dòng còn trống pass
python eval/grade.py eval/run-N.csv --force          # chấm lại cả dòng máy đã chấm; không ghi đè dòng người rà
python eval/grade.py eval/run-N.csv --force-human    # chấm lại cả dòng người rà; giữ nguyên chữ ghi chú của người
python run.py score eval/run-N.csv
python -m unittest discover -s codebase -p "test_*.py"
python run.py simulate --try     # thử mô phỏng chi phí 10 phiên
python run.py simulate           # mô phỏng chi phí → cost/simulate-N.csv
python evidence/count.py         # đếm bằng chứng đã nhập
python evidence/fetch_reviews.py --refresh           # tải lại review (mẫu sẽ khác); giữ dòng human_verified
python evidence/fetch_reviews.py --refresh --allow-partial   # có app lỗi vẫn ghi mẫu từng phần, thoát 0

# Cổng kiểm chất lượng: chỉ cho phát triển, make là tuỳ chọn
python -m pip install -r requirements-dev.txt        # ruff 0.17.4, mypy 2.4.1
make lint                        # ruff check, chỉ đọc
make format                      # ruff format, GHI file (trừ file khung)
make format-check                # kiểm định dạng, không ghi
make typecheck                   # mypy trên codebase eval evidence data
make test                        # unittest, ép MODEL_PROVIDER=fake
make build                       # compileall: kiểm cú pháp, không đóng gói
make verify                      # lint → format-check → typecheck → test → build
```

Khung chỉ dùng thư viện chuẩn của Python. Thêm thư viện thì ghi vào `requirements.txt`. `requirements-dev.txt` chỉ chứa công cụ phát triển; chạy ứng dụng không cần cài gì.

- `python run.py …` vẫn là lệnh chính, chạy được trên Windows. Target thiếu công cụ (ruff, mypy) thì dừng với exit 2 và in lệnh cài; cài công cụ, không bỏ qua cổng kiểm.
- `typecheck` bỏ qua lỗi của ba file khung `tracing`, `run_eval`, `simulate` (overrides trong `pyproject.toml`); `lint` và `format` loại bốn file khung.
- `fetch_reviews.py`: mọi app lỗi → thoát 1, không ghi gì. Một phần app lỗi → cảnh báo, thoát 1, không ghi gì, trừ khi có `--allow-partial` (ghi mẫu từng phần, app lỗi ghi ở `failed_apps` trong `fetch-log.json`). `--refresh` không bao giờ bỏ dòng `human_verified`.
- `fetch_reviews.py`, app lỗi là: lỗi tải (mạng…) hoặc trang 1 trả rỗng. Trang sau trang 1 trả rỗng là hết feed, không phải lỗi: giữ review đã tải của app đó. `reviews.csv` có dòng thừa hoặc thiếu ô → thoát 1, không ghi gì. `reviews.csv`, `fetch-log.json` (và file `--dump`) ghi file tạm hết rồi mới đổi tên cùng đợt; đổi tên lỗi giữa chừng thì thông báo file nào đã đổi.
- `grade.py` in "chưa kết luận" cho §7 trừ khi lượt đầy đủ: đủ mọi câu của bộ câu thử, có câu `tu_choi`, mọi dòng đã chấm và đã kiểm được số, và không phải lượt `run-try` / `run-fake` / `run-mock` / `run-error` / `run-stopped`.

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
- Đáp án: không nói thời gian → tháng hiện tại và nói rõ · hoàn tiền không trừ vào tổng chi · tháng đang dở so cùng kỳ. Ghi chú "hoàn tiền … chưa trừ vào tổng chi" chỉ hiện ở câu trả lời có dòng tổng chi (`tong_chi`, `nhieu_nhat`, `liet_ke` không kèm nhóm), không hiện ở `theo_nhom`, `noi_ban`, `so_sanh` (quyết định A6, 27/11/2026).
- Prompt và code không chứa nguyên văn input của câu thử.

## Bí mật và dữ liệu

- Không đọc, in, log hay dán giá trị trong `.env`; `.env.example` chỉ có tên biến, giá trị trống.
- Key đi trong header, không trong URL; thông báo lỗi phải xoá key trước khi ném ra (lỗi được ghi vào file sẽ commit).
- Chỗ cần dữ liệu từ người ghi `[CHỜ DỮ LIỆU THẬT: …]`; agent không tự điền.
- Chỉ dùng dữ liệu giả lập: không đưa sao kê thật, tên, số điện thoại, số tài khoản thật vào repo hay vào model.
- Test không gọi mạng (`MODEL_PROVIDER=fake`).
