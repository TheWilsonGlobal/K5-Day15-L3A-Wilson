"""Giao diện dòng lệnh: gõ câu hỏi → answer() trong agent.py → câu trả lời, bảng giao dịch, model và token.

Chạy bằng: python run.py   (macOS/Linux có thể là python3, Windows có thể là py)
Đổi nhóm chi chỉ ghi khi người dùng gõ "c" ở bước xác nhận.
"""

import io
import os
import re
import sys
import time

for _stream in (sys.stdout, sys.stderr, sys.stdin):
    if isinstance(
        _stream, io.TextIOWrapper
    ):  # luồng khác (vd StringIO khi thử) không đổi được mã hoá
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

WIDTH = 78
DESC_WIDTH = 34
# Dòng giao dịch do agent._line dựng: "  T0001 · 01/11/2026 · 50.000đ · «mô tả» · Nhóm"
ROW = re.compile(
    r"^  (\w\d{4}) · (\d{2}/\d{2}/\d{4}) · ([\d.]+đ) · «(.*)»(?: · (.+))?$"
)
EXAMPLES = [
    "Tháng này mình tiêu nhiều nhất vào đâu?",
    "So tháng này với tháng trước giúp mình",
    "Những khoản nào tháng này chưa rõ nhóm?",
]


def _where(e):
    """File (trong codebase/) gây lỗi khi nạp: SyntaxError có e.filename, lỗi khác lấy khung cuối của traceback."""
    import traceback

    path = getattr(e, "filename", None) or (
        traceback.extract_tb(e.__traceback__)[-1].filename if e.__traceback__ else ""
    )
    if not path:
        return "codebase/"
    p = os.path.abspath(path)
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.relpath(p, base).replace(os.sep, "/") if p.startswith(base) else path


def _clip(text, width):
    return text if len(text) <= width else text[: width - 1] + "…"


def render(output):
    """Căn các dòng giao dịch thành bảng; mọi chữ và số khác giữ nguyên."""
    out, table = [], []

    def flush():
        if not table:
            return
        amount = max(len(r[2]) for r in table + [("", "", "Số tiền", "", "")])
        desc = max(
            len(_clip(r[3], DESC_WIDTH))
            for r in table + [("", "", "", "Mô tả trên sao kê", "")]
        )
        fmt = "  %%-5s  %%-10s  %%%ds  %%-%ds  %%s" % (amount, desc)
        out.append(
            (fmt % ("Mã", "Ngày", "Số tiền", "Mô tả trên sao kê", "Nhóm")).rstrip()
        )
        out.append("  " + "-" * (5 + 10 + amount + desc + 8 + 8))
        for code, date, money, text, group in table:
            out.append(
                (
                    fmt % (code, date, money, _clip(text, DESC_WIDTH), group or "")
                ).rstrip()
            )
        del table[:]

    for line in output.split("\n"):
        m = ROW.match(line)
        if m:
            table.append(m.groups())
        else:
            flush()
            out.append(line)
    flush()
    return "\n".join(out)


def footer(summary, seconds):
    return (
        "model %s · gọi model %d lần · công cụ %d lần · token vào %d / ra %d · %.1f giây"
        % (
            ", ".join(summary["models"]) or "—",
            summary["model_calls"],
            summary["tool_calls"],
            summary["tokens_in"],
            summary["tokens_out"],
            seconds,
        )
    )


def main() -> int:
    try:
        import tracing
        from agent import answer
        import ai
        import tools

        tools.USE_OVERRIDES = True  # bản chạy thử đọc thay đổi người dùng đã xác nhận; eval và simulate thì không
    except Exception as e:  # lỗi cú pháp, thiếu thư viện… trong codebase/
        print(
            "Không nạp được codebase/ — lỗi ở %s: %s: %s"
            % (_where(e), type(e).__name__, e)
        )
        print("Sửa lỗi rồi chạy lại. Cách nối model: docs/connect-model.md")
        return 1
    mode = (
        "CHẾ ĐỘ GIẢ (chưa nối model)"
        if ai.MODEL_PROVIDER == "fake"
        else "model %s" % ai.MODEL_NAME
    )
    print("=" * WIDTH)
    print("Giải thích chi tiêu từ sao kê · dữ liệu GIẢ LẬP · %s" % mode)
    print(
        "Chỉ đọc và tính: không chuyển tiền, không tư vấn đầu tư. Đừng gõ OTP hay số thẻ."
    )
    print("Thử hỏi: " + " · ".join('"%s"' % q for q in EXAMPLES[:2]))
    print('         "%s"' % EXAMPLES[2])
    print("Thoát: Ctrl+C, hoặc Enter hai lần.")
    print("=" * WIDTH)
    blank = 0
    while True:
        try:
            text = input("\nBạn hỏi > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not text:
            blank += 1
            if blank >= 2:
                return 0
            continue
        blank = 0
        if not sys.stdin.isatty():  # chạy bằng đường ống: in lại câu hỏi cho dễ đọc
            print(text)
        tracing.begin("app")
        started = time.perf_counter()
        try:
            result = answer(text)
        except NotImplementedError as e:
            tracing.end()
            print("Chưa nối model: %s" % e)
            return 1
        except Exception as e:  # báo rồi cho hỏi tiếp; phân loại theo chỗ lỗi xảy ra
            _, events = tracing.end()
            # lỗi thoát ra khỏi call_model đều được model_call ghi vào trace (kind "model", có error)
            if any(ev["kind"] == "model" and ev.get("error") for ev in events):
                print("Mình chưa trả lời được vì lỗi gọi model. Thử lại sau ít giây.")
                print("[lỗi] model: %s: %s" % (type(e).__name__, e))
            else:  # đọc dữ liệu, file sửa, mã trong codebase/: không phải lỗi của model
                print(
                    "Mình chưa trả lời được vì lỗi cục bộ (dữ liệu hoặc file sửa), không phải lỗi model."
                )
                print("[lỗi] cục bộ: %s: %s" % (type(e).__name__, e))
            continue
        summary, _ = tracing.end()
        print("-" * WIDTH)
        print(render(result.get("output", "")))
        print("-" * WIDTH)
        print(footer(summary, time.perf_counter() - started))
        draft = result.get("draft")
        if draft:  # chỗ người duyệt: chỉ ghi khi người dùng gõ "c"
            try:
                ok = (
                    input("Ghi thay đổi này? (c = có / Enter = không) ").strip().lower()
                    == "c"
                )
            except (EOFError, KeyboardInterrupt):
                ok = False
            if ok:
                try:
                    tools.apply_override(draft["tx_id"], draft["category"])
                except (
                    OSError,
                    ValueError,
                ) as e:  # ghi lỗi hoặc file sửa cũ hỏng: báo, không dừng chương trình
                    print(
                        "[lỗi] không ghi được thay đổi: %s: %s" % (type(e).__name__, e)
                    )
                else:
                    print("Đã ghi vào data/overrides.json (xoá file để hoàn tác).")
            else:
                print("Không ghi gì.")


if __name__ == "__main__":
    sys.exit(main())
