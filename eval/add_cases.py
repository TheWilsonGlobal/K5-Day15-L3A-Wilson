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
import oracle  # noqa: E402

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
    new = [drafts[i] for i in ids]
    repeated = sorted({r["input"] for r in new} & {r["input"] for r in old})
    if repeated:
        raise ValueError("trùng câu hỏi đã có: %s" % repeated[0])
    total = len(old) + len(new)
    real = sum(map(is_real, old + new))
    if real * 3 < total:
        raise ValueError("sau khi thêm chỉ có %d/%d câu từ nguồn thật (cần ≥ 1/3): bớt câu tu_viet" % (real, total))
    with open(bench, "rb") as f:
        raw = f.read()
    end = "\r\n" if b"\r\n" in raw else "\n"
    out = io.StringIO()
    csv.DictWriter(out, fieldnames=fields, lineterminator=end).writerows(new)
    with open(bench, "ab") as f:
        f.write((b"" if raw.endswith(b"\n") else end.encode()) + out.getvalue().encode("utf-8"))
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
    print("Đã thêm %d câu → %d câu, %d từ nguồn thật. Đã ghi lại eval/oracle.json." % (len(args), total, real))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
