# Wilson — Giải thích chi tiêu từ sao kê

**Thành viên, lớp, track:** xem [TEAMS.md](TEAMS.md).

**Lát cắt:** một nhân viên văn phòng trẻ hỏi bằng tiếng Việt về chi tiêu của mình · AI chọn khoảng thời gian và công cụ, gán "không rõ" khi giao dịch không đủ căn cứ · người dùng nhận câu trả lời có số do code tính, kèm bảng giao dịch dẫn chứng và sửa được nhóm chi. Dữ liệu là sao kê giả lập; thiết kế ở [spec.md](spec.md) §4.

**Không làm:** chuyển tiền hay giao dịch hộ · tư vấn đầu tư · xem chi tiêu của người khác · nhận sao kê thật.

---

## Nhóm làm gì, khung làm gì

| Nhóm quyết định và viết | Khung làm sẵn (không cần sửa) |
|---|---|
| Người dùng, pain, bằng chứng, impact (`evidence/`, `spec.md` §1–§2) | — |
| Hình dạng giải pháp, công cụ, prompt, luồng (`spec.md` §4, `codebase/agent.py`, `tools.py`, `ai.py`) | Ghi mọi lần gọi model / công cụ vào trace, cộng token (`codebase/tracing.py`) |
| Bộ câu thử, metric, chuẩn "đạt" (`eval/benchmark.csv`, `eval/metric_spec.yaml`, `spec.md` §7) | Kiểm đủ cột, đủ câu `kho` / `tu_choi`, đủ ≥1/3 câu từ người dùng / data thật (`run.py check`) |
| Chấm cột `pass` theo metric spec | Chạy cả bộ một lệnh, có run ID, model, token từng câu (`run.py eval`) · tính % đạt (`run.py score`) |
| Persona, số người dùng thật, giá model (`cost/personas.yaml`) | Sinh ~50 phiên, chạy thật qua bản chạy thử, tính chi phí / phiên, / task thành công, / tháng 3 kịch bản (`run.py simulate`) |

*Ví dụ track A (ví dụ cỡ, không phải lời giải):* nhóm viết công cụ `search_lesson` tra bài pre-class đã đánh mã đoạn, luồng "tra đoạn → model trả lời kèm mã đoạn, không có thì nói không có", metric "mọi khẳng định có mã đoạn đúng", persona "ôn dồn trước kiểm tra". Khung chạy 25 câu thử ra `run-1.csv`, nhóm chấm `pass`, `score` in % đạt; `simulate` chạy 50 phiên ra chi phí / task thành công cho hai model.

## Chạy trong 3 phút

Bộ khung cần **Python 3.10 trở lên** (Python 3.9 có sẵn trên macOS vẫn chạy được, chỉ in một dòng nhắc). **Không cần `pip install`.**

**Bước 1 — Mở cửa sổ lệnh ngay trong thư mục repo**

| Windows (PowerShell) | macOS |
|---|---|
| Mở thư mục repo bằng File Explorer → bấm vào thanh địa chỉ → gõ `powershell` → Enter | Mở **Terminal** (Cmd + Space, gõ "Terminal") → gõ `cd ` (có dấu cách) → kéo thả thư mục repo vào → Enter |

Gõ `dir` (Windows) hoặc `ls` (macOS / Linux): thấy `run.py` và `README.md` là đang đứng đúng chỗ.

**Bước 2 — Kiểm Python và chạy thử**

| Việc | Windows (PowerShell) | macOS / Linux |
|---|---|---|
| Kiểm Python | `python --version` (không được thì `py --version`) | `python3 --version` |
| Chạy bản chạy thử (chế độ giả, chưa gọi model) | `python run.py` | `python3 run.py` |
| Kiểm bộ câu thử | `python run.py check` | `python3 run.py check` |
| Tạo file `.env` để nối model | `copy .env.example .env` | `cp .env.example .env` |

- Windows: gõ `python` mà mở Microsoft Store hoặc báo không có lệnh → dùng `py`. Chưa có Python: cài từ python.org, **tick "Add python.exe to PATH"**, mở lại PowerShell.
- macOS: báo `command not found: python` là bình thường → dùng `python3`.
- Chưa có `.env`: `python run.py` chạy chế độ giả, câu trả lời mở đầu bằng `[GIẢ]` và luôn giống nhau.
- Chạy model thật: trong `.env` điền `MODEL_PROVIDER` (`gemini` hoặc `groq`), `MODEL_NAME`, `API_KEY`; tuỳ chọn `API_KEYS` (khoá dự phòng cách nhau dấu phẩy, dùng khi gặp HTTP 429). Không commit `.env`.
- Thử hỏi: `Trong tháng 10 mình chi tất cả bao nhiêu?` · `Tiền ăn uống ngốn mất bao nhiêu rồi?`

Trong README này lệnh viết là `python …`; máy nhóm cần `python3` hay `py` thì gõ thay.

## Lệnh

| Lệnh | Làm gì |
|---|---|
| `python run.py` | Chạy bản chạy thử (gõ đầu vào, nhận kết quả, kèm số lần gọi model / token) |
| `python run.py check` | Kiểm `eval/benchmark.csv` (6 cột, số câu, `kho` / `tu_choi`, mã `source`, ô trống, dòng mẫu) `eval/metric_spec.yaml` (≥3 metric điền đủ) và `TEAMS.md` (đúng format để BTC quét). Chỉ cảnh báo, không sửa file |
| `python run.py eval --try` | **Thử nối model:** chạy 3 câu đầu (`--try 5` = 5 câu) → `eval/run-try.csv`. Thấy "Nối model được" là xong. Không tính là một lượt |
| `python run.py eval` | Chạy cả bộ qua `codebase/agent.py` → `eval/run-1.csv` (lần sau `run-2.csv`…) + `traces/run-1.jsonl`. Mỗi dòng có run ID, model, số lần gọi model / công cụ, token. Model còn giả → chỉ ghi `run-mock.csv`; mọi câu lỗi → `run-error.csv`; Ctrl+C → `run-stopped.csv` — đều **không** được đánh số |
| `python run.py eval --fake` | Thử riêng bộ chạy, không gọi agent → `eval/run-fake.csv` |
| `python run.py score eval/run-1.csv` | Sau khi điền cột `pass` (1 / 0): in % đạt tổng và theo `type`. Còn ô trống → "CHƯA CHẤM XONG", không in % |
| `python run.py simulate --try` | Thử mô phỏng chi phí 10 phiên (làm trước CP3) → `cost/simulate-try.csv` |
| `python run.py simulate` | Mô phỏng chi phí khi dùng thật theo `cost/personas.yaml` (≥50 phiên) → `cost/simulate-N.csv` + `cost/simulate-N-summary.md` |
| `python eval/grade.py eval/run-1.csv` | Chấm một lượt theo `eval/metric_spec.yaml`: chỉ điền `pass`, `ghi_chu`; người rà lại. Chỉ chấm dòng còn trống `pass`. Kết luận §7 in "chưa kết luận" khi lượt chưa đủ điều kiện (xem dưới bảng) |
| `python eval/grade.py eval/run-1.csv --force` | Chấm lại cả dòng do `grade.py` đã chấm; không bao giờ ghi đè dòng người đã rà |
| `python eval/grade.py eval/run-1.csv --force-human` | Như `--force` và chấm lại cả dòng người đã rà; chữ ghi chú của người giữ nguyên văn |
| `python eval/add_cases.py C11 C12 …` | Thêm câu đã duyệt từ `eval/benchmark-draft.csv` vào bộ câu thử và ghi lại `eval/oracle.json` |
| `python eval/oracle.py` · `python eval/oracle.py --json` | Đáp án độc lập theo tháng và nhóm · ghi `eval/oracle.json` |
| `python evidence/fetch_reviews.py` | Tải review công khai theo `evidence/data-mining.md` §1a (đã có mẫu thì không ghi đè nếu thiếu `--refresh`). App lỗi (lỗi tải hoặc trang 1 trả rỗng) thì thoát 1, không ghi file nào; trang sau trang 1 trả rỗng là hết feed, giữ review đã tải. `reviews.csv` có dòng thừa hoặc thiếu ô thì thoát 1, không ghi gì. Các file đầu ra (`reviews.csv`, `fetch-log.json`, file `--dump`) ghi file tạm hết rồi mới đổi tên cùng đợt; đổi tên lỗi giữa chừng thì thông báo file nào đã đổi |
| `python evidence/fetch_reviews.py --refresh` | Tải lại khi đã có mẫu (mẫu sẽ khác); không bao giờ bỏ dòng `human_verified` |
| `python evidence/fetch_reviews.py --refresh --allow-partial` | Chỉ một phần app lỗi: cảnh báo, ghi mẫu từng phần, thoát 0; app lỗi ghi ở `failed_apps` trong `evidence/fetch-log.json`. Mọi app đều lỗi thì vẫn thoát 1, không ghi gì |
| `python evidence/count.py` | Đếm phỏng vấn và review đã nhập: x/n, trích dẫn, chỗ còn thiếu |
| `python data/generate.py` | Sinh lại dữ liệu giả lập (cùng seed ra cùng file) |
| `python -m unittest discover -s codebase -p "test_*.py"` | Test, không gọi mạng |
| `python run.py simulate --rate-from eval/run-2.csv` | Như trên, lấy tỉ lệ đạt từ đúng lượt chỉ định. Không ghi thì khung lấy lượt `run-N` mới nhất đã chấm, cùng model, và ghi rõ đã lấy lượt nào trong bản tóm tắt |

Gói miễn phí báo hết lượt: thêm `--wait 4` sau `eval` hoặc `simulate` (nghỉ 4 giây giữa hai lượt gọi). Sửa CSV bằng Excel: *File → Save As → CSV UTF-8*; Google Sheets: *Tệp → Tải xuống → CSV*.

**Lượt có lỗi kỹ thuật** (cột `error` có chữ): không sửa tay file đó, chạy lại thành lượt mới và ghi vào bảng các lượt ở `eval/README.md`. Không xoá file lượt nào.

**Kết luận §7 của `grade.py`:** chỉ đưa ra khi lượt đầy đủ: đủ mọi câu của bộ câu thử, có câu `tu_choi`, mọi dòng đã chấm và đã kiểm được số (có trace, không lỗi kỹ thuật), và không phải lượt `run-try` / `run-fake` / `run-mock` / `run-error` / `run-stopped`. Thiếu một điều thì in "chưa kết luận".

### Cổng kiểm chất lượng (tuỳ chọn, chỉ khi phát triển)

Chạy ứng dụng **không cần cài gì** (chỉ dùng thư viện chuẩn). Muốn dùng các cổng kiểm thì cài công cụ phát triển (ruff 0.17.4, mypy 2.4.1):

```
python -m pip install -r requirements-dev.txt
```

| Lệnh | Làm gì |
|---|---|
| `make lint` | `ruff check`, chỉ đọc |
| `make format` | `ruff format`, **ghi** vào file; file khung được loại ra |
| `make format-check` | Kiểm định dạng, không ghi |
| `make typecheck` | `mypy` trên `codebase`, `eval`, `evidence`, `data`; lỗi ở file khung `tracing`, `run_eval`, `simulate` được bỏ qua theo `pyproject.toml` |
| `make test` | Chạy unittest, ép `MODEL_PROVIDER=fake` |
| `make build` | `compileall`: chỉ kiểm cú pháp, không đóng gói |
| `make verify` | Lần lượt `lint` → `format-check` → `typecheck` → `test` → `build`, dừng ở chặng lỗi đầu tiên |

`make` là tuỳ chọn: `python run.py …` vẫn là lệnh chính và chạy được trên Windows. Thiếu công cụ thì target dừng với exit 2 và in lệnh cài. Máy dùng lệnh Python khác thì ghi đè, ví dụ `make PY=py verify`.

Nhóm dùng stack khác (Node, Streamlit, notebook…): sửa hàm `run_app()` trong `run.py` để `python run.py` vẫn chạy được bản chạy thử, và giữ `answer()` trong `codebase/agent.py` để `eval`, `simulate` chạy được.

## Bản chạy thử — viết ở đâu

| File | Nội dung |
|---|---|
| `codebase/agent.py` | `answer(text)`: workflow cố định, tối đa 2 lần gọi model, kiểm số trước khi trả lời |
| `codebase/tools.py` | Công cụ đọc và tính, mỗi hàm một `@tool`; mọi phép tính nằm ở đây |
| `codebase/ai.py` | `call_model(system, user)`: Gemini, Groq hoặc chế độ giả |
| `codebase/app.py` | Giao diện dòng lệnh, bước người dùng xác nhận khi đổi nhóm chi |

Bộ chạy gửi **nguyên ô `input`** của câu thử vào `answer(text)`. Dữ liệu nằm ở `data/`, chỉ đọc qua công cụ.

## Phần nào thật, phần nào giả

| Thành phần | Thật / Giả | Ghi chú |
|---|---|---|
| Lời gọi AI ở quyết định trung tâm | **Thật** khi có `.env` | `gemini-3.5-flash-lite`: hiểu câu hỏi và gán nhóm mô tả lạ. Nhánh `groq` cũng đã thử. Không có `.env` thì giả (`[GIẢ]`) |
| Tính tổng, so sánh, câu trả lời | Thật | Code tính và dựng từ mẫu; model không viết con số |
| Sao kê và người dùng | **Giả** | Synthetic, tự sinh (`data/DATA_CARD.md`); không kết nối ngân hàng hay ví |
| Đăng nhập | **Giả** | Người dùng cố định `U001` |
| Ngày "hôm nay" | **Giả** | Cố định 27/11/2026 |
| Đổi nhóm chi | Thật, cục bộ | Chỉ ghi `data/overrides.json` sau khi người dùng xác nhận trong `app.py` |

## Dùng AI vào việc gì

Nhóm dùng Claude Code để soạn dữ liệu giả lập, code, test, bộ câu thử nháp và tài liệu. Phần người kiểm lại: [CHỜ DỮ LIỆU THẬT]. Chi tiết: [docs/ai-usage.md](docs/ai-usage.md). Coding agent đọc [AGENTS.md](AGENTS.md).

## File mẫu — điền ở bước nào

| File | Điền ở bước guide | Mốc |
|---|---|---|
| `TEAMS.md` | 1.0 | CP1 · **đúng format**, BTC quét khi chấm |
| `canvas.md` | 1.4 | CP1, cập nhật CP2 |
| `evidence/hypothesis.md` | 1.1 | trước khi tìm bằng chứng |
| `evidence/data-mining.md` · `evidence/interviews/TEMPLATE.md` → `P1.md`… · `evidence/survey/TEMPLATE.md` | 1.2 | bắt đầu sau Zoom, xong CP3 |
| `evidence/summary.md` | 1.2 | CP3 |
| `spec.md` | §0–§2: 1.1–1.3 · §3–§5: 2.1–2.3 · §7: 2.4 · §8: 4.2 · §10: suốt | §7 chốt CP2 · §0–§7 CP3 · đủ CP4 |
| `data/DATA_CARD.md` | 2.4 | bản đầu CP2 |
| `eval/benchmark.csv` · `eval/metric_spec.yaml` | 2.4 | ≥10 câu + metric chốt CP2 · 20–30 câu CP3 |
| `codebase/` | 3.2, 3.3 | khung CP2 · AI thật CP3 |
| `eval/report.md` · `eval/README.md` | 4.1 (README mục 1–4 từ 2.4) | CP4 |
| `cost/personas.yaml` · `cost/cost-estimate.md` | 4.2 | thử 10 phiên CP3 · đủ CP4 |
| `validation/log.md` *(bonus)* | 4.3 | CP4 |
| `slides/outline.md` → `demo-slides.pdf` | 5.1 | CP4 |
| `reflection/TEMPLATE.md` → `reflection/<ten>.md` | 5.3 | 23:59 Thứ Bảy 28/11 |
| `AGENTS.md` · `docs/ai-usage.md` | khi dùng coding agent / AI | suốt |

## Bảy hạng mục bắt buộc — nằm ở file nào

| # | Hạng mục | File |
|---|---|---|
| 1 | Bằng chứng pain | `evidence/` (tổng hợp ở `evidence/summary.md`) |
| 2 | Impact có số | `spec.md` §2 |
| 3 | Thiết kế giải pháp | `spec.md` §4 |
| 4 | Bản chạy thử làm trọn lát cắt | `codebase/` · lệnh ở mục "Lệnh" |
| 5 | Định nghĩa "tốt" + bộ câu thử | `data/DATA_CARD.md` · `eval/` |
| 6 | Mô phỏng chi phí khi dùng thật | `cost/` |
| 7 | Slide + demo + video dự phòng | slide trong repo (PDF, PPTX, HTML…) hoặc link slide ở form CP4 · link video: [CHỜ DỮ LIỆU THẬT] |
| + | *Bonus:* người dùng thử | `validation/log.md` |
