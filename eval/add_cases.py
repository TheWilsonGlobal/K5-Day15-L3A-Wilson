"""Chép câu đã được người duyệt từ eval/benchmark-draft.csv vào cuối eval/benchmark.csv rồi ghi lại oracle.json.

    python eval/add_cases.py C11 C12 C13

Chỉ thêm: không sửa, không xoá dòng đã có. Từ chối nếu sau khi thêm, câu từ nguồn thật dưới 1/3.
"""

import csv
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import oracle  # noqa: E402  # import sau khi thêm eval/ vào sys.path

DRAFT = os.path.join(HERE, "benchmark-draft.csv")
REAL = ("nguoi_dung", "data_that")


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def is_real(row):
    return row["source"].split(":")[0].strip() in REAL


def add(ids, bench=oracle.BENCH, draft=DRAFT):
    """→ (tổng số câu, số câu nguồn thật). Báo ValueError và không ghi gì khi không hợp lệ."""
    fields, old = read(bench)
    drafts = {r["id"]: r for r in read(draft)[1]}
    have = {r["id"] for r in old}
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("cần danh sách mã câu, không lặp")
    unknown = [i for i in ids if i not in drafts]
    if unknown:
        raise ValueError("không có trong file nháp: %s" % ", ".join(unknown))
    again = [i for i in ids if i in have]
    if again:
        raise ValueError("đã có trong bộ câu thử: %s" % ", ".join(again))
    answers = oracle.cases(have | set(ids))
    unanswered = [i for i in ids if i not in answers]
    if unanswered:
        raise ValueError(
            "chưa có đáp án trong eval/oracle.py: %s" % ", ".join(unanswered)
        )
    new = [drafts[i] for i in ids]
    inputs = [r["input"] for r in new]
    twice = sorted({i for i in inputs if inputs.count(i) > 1})
    if twice:
        raise ValueError("các câu mới trùng câu hỏi với nhau: %s" % twice[0])
    repeated = sorted({r["input"] for r in new} & {r["input"] for r in old})
    if repeated:
        raise ValueError("trùng câu hỏi đã có: %s" % repeated[0])
    total = len(old) + len(new)
    real = sum(map(is_real, old + new))
    if real * 3 < total:
        raise ValueError(
            "sau khi thêm chỉ có %d/%d câu từ nguồn thật (cần ≥ 1/3): bớt câu tu_viet"
            % (real, total)
        )
    with open(bench, "rb") as f:
        raw = f.read()
    end = "\r\n" if b"\r\n" in raw else "\n"
    out = io.StringIO()
    csv.DictWriter(out, fieldnames=fields, lineterminator=end).writerows(new)
    gap = b"" if raw.endswith(b"\n") else end.encode()
    oracle.write_atomic(bench, raw + gap + out.getvalue().encode("utf-8"))
    return total, real


def main(args):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    try:
        total, real = add(args)
    except ValueError as error:
        print("Không thêm gì: %s" % error)
        return 1
    oracle.write_json()
    print(
        "Đã thêm %d câu → %d câu, %d từ nguồn thật. Đã ghi lại eval/oracle.json."
        % (len(args), total, real)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
