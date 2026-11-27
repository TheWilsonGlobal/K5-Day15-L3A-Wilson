"""Đáp án độc lập cho câu thử. KHÔNG import codebase/tools.py và không dùng quy tắc của nó:
tính từ data/transactions.csv + nhãn thật data/labels.csv.

    python eval/oracle.py                                   bảng chi theo tháng và nhóm
    python eval/oracle.py 2026-11-01 2026-11-27             tổng một khoảng
    python eval/oracle.py 2026-11-01 2026-11-27 an_uong     một nhóm trong khoảng
"""
import csv
import os
import sys

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _read(name):
    with open(os.path.join(DATA, name), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load():
    labels = {r["tx_id"]: r for r in _read("labels.csv")}
    rows = []
    for r in _read("transactions.csv"):
        rows.append(dict(r, amount_vnd=int(r["amount_vnd"]), **{k: labels[r["tx_id"]][k]
                    for k in ("kind", "category", "merchant", "tag")}))
    return rows


def spending(date_from, date_to, category=None, merchant=None, user="U001"):
    """Các khoản CHI của một người trong khoảng ngày (tính cả hai đầu)."""
    return [r for r in load()
            if r["user_id"] == user and r["kind"] == "chi" and date_from <= r["date"] <= date_to
            and (category is None or r["category"] == category)
            and (merchant is None or r["merchant"] == merchant)]


def total(date_from, date_to, category=None, merchant=None, user="U001"):
    """→ (tổng tiền, số giao dịch)."""
    rows = spending(date_from, date_to, category, merchant, user)
    return sum(r["amount_vnd"] for r in rows), len(rows)


def by_category(date_from, date_to, user="U001"):
    """→ {nhóm: (tổng tiền, số giao dịch)}, xếp từ nhiều đến ít."""
    out = {}
    for r in spending(date_from, date_to, user=user):
        amount, n = out.get(r["category"], (0, 0))
        out[r["category"]] = (amount + r["amount_vnd"], n + 1)
    return dict(sorted(out.items(), key=lambda kv: (-kv[1][0], kv[0])))


def change(a, b):
    """Chênh lệch từ a sang b → (tăng/giảm/bằng, số tiền, phần trăm làm tròn 1 chữ số)."""
    word = "tang" if b > a else ("giam" if b < a else "bang")
    return word, abs(b - a), round(abs(b - a) * 100.0 / a, 1) if a else None


def main(args):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if args:
        amount, n = total(args[0], args[1], args[2] if len(args) > 2 else None)
        print("%s → %s %s: %d đ (%d giao dịch)" % (args[0], args[1], args[2] if len(args) > 2 else "tất cả", amount, n))
        return 0
    for start, end in (("2026-09-01", "2026-09-30"), ("2026-10-01", "2026-10-31"), ("2026-11-01", "2026-11-27")):
        amount, n = total(start, end)
        print("\n%s → %s: %d đ (%d giao dịch)" % (start, end, amount, n))
        for category, (value, count) in by_category(start, end).items():
            print("  %-10s %12d đ  (%d)" % (category, value, count))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
