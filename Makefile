# TUỲ CHỌN, chỉ cho máy có sẵn make. Lệnh chính là `python run.py …` (chạy được cả trên Windows).
# Các target run, check, eval, eval-try, score, simulate, simulate-try chỉ gọi lại run.py.
# Các target kiểm chất lượng (lint, format, format-check, typecheck, test, build, verify) là của nhóm:
#   - Cần công cụ dev (ruff, mypy): python -m pip install -r requirements-dev.txt
#     Ứng dụng KHÔNG cần cài gì: bộ khung chạy bằng thư viện chuẩn.
#   - Công cụ thiếu thì target dừng với lỗi (exit khác 0) và in lệnh cài; không bỏ qua im lặng.
#   - "build" của một app chỉ dùng thư viện chuẩn nghĩa là cổng kiểm cú pháp (biên dịch bytecode), KHÔNG phải đóng gói.
#     Nó chỉ ghi __pycache__, đã nằm trong .gitignore.
#   - File khung (run.py, codebase/tracing.py, eval/run_eval.py, cost/simulate.py) không bị sửa bởi bất kỳ target nào.
# PY: trên Windows mặc định là python (python3 thường là lối tắt của Store, không chạy được); nơi khác là python3.
#   Ghi đè: make PY=py   hoặc   make PY=C:\duong\dan\python.exe

ifeq ($(OS),Windows_NT)
PY ?= python
else
PY ?= python3
endif

# Mã của nhóm và file khung. run.py được liệt kê nhưng pyproject.toml loại nó ra khỏi ruff.
SRC = codebase eval evidence data cost run.py

# Kiểm công cụ có import được không (True/rỗng). Tính lười: chỉ khi một target cần.
HAS_RUFF = $(findstring True,$(shell $(PY) -c "import importlib.util as u; print(u.find_spec('ruff') is not None)"))
HAS_MYPY = $(findstring True,$(shell $(PY) -c "import importlib.util as u; print(u.find_spec('mypy') is not None)"))
MISS_RUFF = Thiếu ruff trong $(PY). Cài bằng: $(PY) -m pip install -r requirements-dev.txt
MISS_MYPY = Thiếu mypy trong $(PY). Cài bằng: $(PY) -m pip install -r requirements-dev.txt

run: ; $(PY) run.py
check: ; $(PY) run.py check
eval: ; $(PY) run.py eval
eval-try: ; $(PY) run.py eval --try
score: ; $(PY) run.py score $(RUN)
simulate: ; $(PY) run.py simulate
simulate-try: ; $(PY) run.py simulate --try

# Lint bằng ruff, chỉ đọc (không --fix).
lint:
	$(if $(HAS_RUFF),$(PY) -m ruff check $(SRC),$(error $(MISS_RUFF)))

# Ghi định dạng bằng ruff format. Đây là target duy nhất ghi file mã nguồn.
format:
	$(if $(HAS_RUFF),$(PY) -m ruff format $(SRC),$(error $(MISS_RUFF)))

# Chỉ kiểm định dạng, không ghi; thoát khác 0 nếu có file sẽ bị đổi.
format-check:
	$(if $(HAS_RUFF),$(PY) -m ruff format --check $(SRC),$(error $(MISS_RUFF)))

# Kiểm kiểu bằng mypy trên mã của nhóm (không gồm file khung, xem [tool.mypy] trong pyproject.toml).
typecheck:
	$(if $(HAS_MYPY),$(PY) -m mypy codebase eval evidence data,$(error $(MISS_MYPY)))

# Chạy bộ unittest. MODEL_PROVIDER=fake: test không gọi mạng, kể cả khi .env có key thật.
test: export MODEL_PROVIDER := fake
test:
	$(PY) -m unittest discover -s codebase -p "test_*.py"

# Biên dịch kiểm cú pháp mọi nguồn (xem ghi chú "build" ở đầu file).
build:
	$(PY) -m compileall -q $(SRC)

# Gộp: lint, format-check, typecheck, test, build. Dừng ở chặng đầu tiên lỗi.
verify: lint format-check typecheck test build

.PHONY: run check eval eval-try score simulate simulate-try lint format format-check typecheck test build verify
