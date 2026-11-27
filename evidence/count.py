"""Đếm bằng chứng từ file nhóm điền tay. Không tạo, không đoán số: ô trống thì báo trống.

    python evidence/count.py                    in tổng hợp ra màn hình
    python evidence/count.py > kết-quả.md       rồi chép số vào evidence/summary.md

Đọc:
  evidence/reviews.csv              mỗi review một dòng (cách đếm: evidence/data-mining.md §1)
  evidence/reviews-check.csv        (tuỳ chọn) người thứ hai gắn nhãn: cột ma,nhan
  evidence/interviews/P*.md         mỗi người một file (mẫu: interviews/TEMPLATE.md)
"""
import csv
import glob
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
COLUMNS = ["ma", "app", "kho", "link", "ngay_xem", "ngay_review", "so_sao", "trich", "nhan", "nguoi_gan"]
MAIN = ["kho_hieu_gd", "kho_tong_hop", "kho_tim_gd"]   # tính vào số chính
SIDE = ["ngan_sach", "gd_bi_chan"]                      # đếm riêng (hướng E2, E3)
LABELS = MAIN + SIDE + ["khac"]
MIN_REVIEWS, MIN_PEOPLE = 30, 3
PERSONAL = re.compile(r"\d[\d .-]{7,}\d|[\w.+-]+@[\w-]+\.\w+")
PAIN = {"co": "co", "khong": "khong", "mot phan": "mot_phan", "mot_phan": "mot_phan"}
FIELDS = {"gap_pain": "Gặp pain", "so_lan_thang": "Số lần / 1 tháng qua", "so_phut": "Số phút lần gần nhất",
          "lan_gan_nhat": "Lần gần nhất", "xoay_xo": "Đang xoay xở bằng"}


def fold(text):
    s = unicodedata.normalize("NFD", (text or "").strip().lower().replace("đ", "d"))
    return "".join(c for c in s if not unicodedata.combining(c))


def read_csv(path):
    if not os.path.exists(path):
        return [], []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader if any((v or "").strip() for v in r.values() if isinstance(v, str))]
        return reader.fieldnames or [], rows


def count_reviews(path, check_path=None):
    """→ dict kết quả đếm review."""
    fields, rows = read_csv(path)
    problems = []
    if fields and fields != COLUMNS:
        problems.append("reviews.csv phải có đúng các cột: %s" % ",".join(COLUMNS))
        rows = []
    clean = [{k: (r.get(k) or "").strip() for k in COLUMNS} for r in rows]
    codes = [r["ma"] for r in clean]
    for code in sorted({c for c in codes if codes.count(c) > 1 or not c}):
        problems.append("mã review trống hoặc trùng: %r" % code)
    for r in clean:
        if not r["nhan"]:
            problems.append("%s chưa gắn nhãn" % r["ma"])
        elif r["nhan"] not in LABELS:
            problems.append("%s có nhãn lạ: %s" % (r["ma"], r["nhan"]))
        for column in ("link", "ngay_xem", "trich"):
            if not r[column]:
                problems.append("%s thiếu cột %s" % (r["ma"], column))
        if PERSONAL.search(r["trich"]):
            problems.append("%s: trích dẫn có chuỗi giống số điện thoại / tài khoản / email, che trước khi commit" % r["ma"])
    labelled = [r for r in clean if r["nhan"] in LABELS]
    result = {
        "n": len(clean), "labelled": len(labelled), "problems": problems,
        "main": sum(r["nhan"] in MAIN for r in labelled),
        "by_label": {label: sum(r["nhan"] == label for r in labelled) for label in LABELS},
        "by_app": {}, "quotes": [r for r in labelled if r["nhan"] in MAIN], "agree": None,
    }
    for r in labelled:
        hit, n = result["by_app"].get(r["app"], (0, 0))
        result["by_app"][r["app"]] = (hit + (r["nhan"] in MAIN), n + 1)
    if check_path and os.path.exists(check_path):
        second = {(r.get("ma") or "").strip(): (r.get("nhan") or "").strip() for r in read_csv(check_path)[1]}
        pairs = [(r["nhan"], second[r["ma"]]) for r in labelled if second.get(r["ma"])]
        result["agree"] = (sum(a == b for a, b in pairs), len(pairs))
    return result


def _field(text, label):
    m = re.search(r"(?im)^[ \t]*[-*][ \t]*%s[ \t]*:[ \t]*(.*)$" % re.escape(label), text)
    value = m.group(1).strip() if m else ""
    return "" if not value or "__" in value or value.startswith("[CHỜ") else value


def read_interview(path):
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    code = os.path.splitext(os.path.basename(path))[0]
    head = text.split("\n", 1)[0].lstrip("# ").split("·")
    role = head[1].strip() if len(head) > 1 else ""
    person = {"ma": code, "vai": "" if role.startswith("[") else role}
    for key, label in FIELDS.items():
        person[key] = _field(text, label)
    person["gap_pain"] = PAIN.get(fold(person["gap_pain"]).strip(" ."), "")
    section = re.search(r"(?ms)^## Trích nguyên văn[^\n]*\n(.*?)(?=^## |\Z)", text)
    quotes = re.findall(r"(?m)^[ \t]*[-*][ \t]*[\"“](.+?)[\"”]", section.group(1)) if section else []
    person["quotes"] = [q.strip() for q in quotes if q.strip() not in ("", "…", "...")]
    person["personal"] = bool(PERSONAL.search(text.split("\n", 1)[-1]))
    return person


def count_interviews(folder):
    people = [read_interview(p) for p in sorted(glob.glob(os.path.join(folder, "P*.md")))
              if re.fullmatch(r"P\d+\.md", os.path.basename(p))]
    problems = []
    for p in people:
        if not p["vai"]:
            problems.append("%s: dòng tiêu đề chưa ghi vai" % p["ma"])
        if not p["gap_pain"]:
            problems.append("%s: chưa ghi \"Gặp pain: co / khong / mot phan\"" % p["ma"])
        if not p["quotes"]:
            problems.append("%s: chưa có trích nguyên văn" % p["ma"])
        if p["personal"]:
            problems.append("%s: có chuỗi giống số điện thoại / tài khoản / email" % p["ma"])
    n = len(people)
    x = sum(p["gap_pain"] == "co" for p in people)
    if n < MIN_PEOPLE:
        verdict = "chưa đủ người (cần ≥%d)" % MIN_PEOPLE
    elif any(not p["gap_pain"] for p in people):
        verdict = "chưa kết luận: còn file chưa ghi \"Gặp pain\""
    elif x >= 3 and x * 4 >= 3 * n:
        verdict = "ĐẠT ngưỡng giả thuyết (≥3 người và ≥75%)"
    elif x < 2:
        verdict = "giả thuyết SAI (dưới 2 người kể được) → xem evidence/hypothesis.md"
    else:
        verdict = "chưa đạt ngưỡng giả thuyết"
    return {"n": n, "x": x, "partial": sum(p["gap_pain"] == "mot_phan" for p in people),
            "people": people, "problems": problems, "verdict": verdict}


def report(reviews, interviews):
    out = ["# Đếm bằng chứng (python evidence/count.py)", "", "## Phỏng vấn"]
    if not interviews["n"]:
        out.append("[CHỜ DỮ LIỆU THẬT: chưa có file evidence/interviews/P*.md]")
    else:
        out += ["", "**%d/%d người** kể được một lần cụ thể (một phần: %d). Kết luận: %s."
                % (interviews["x"], interviews["n"], interviews["partial"], interviews["verdict"]), "",
                "| Mã | Vai | " + " | ".join(FIELDS.values()) + " |", "|---|---|" + "---|" * len(FIELDS)]
        for p in interviews["people"]:
            out.append("| %s | %s | %s |" % (p["ma"], p["vai"] or "—", " | ".join(p[k] or "—" for k in FIELDS)))
        out += [""] + ["- \"%s\" — %s (%s)" % (q, p["ma"], p["vai"] or "chưa ghi vai")
                       for p in interviews["people"] for q in p["quotes"]]
    out += ["", "## Review công khai"]
    n = reviews["n"]
    if not n:
        out.append("[CHỜ DỮ LIỆU THẬT: evidence/reviews.csv chưa có dòng nào]")
    elif reviews["labelled"] < n:
        out.append("Mới gắn nhãn %d/%d dòng: chưa tính x/N." % (reviews["labelled"], n))
    else:
        out.append("")
        out.append("**%d/%d review (%.0f%%)** kể khó khăn khi xem, hiểu hoặc tổng hợp giao dịch.%s"
                   % (reviews["main"], n, 100.0 * reviews["main"] / n,
                      "" if n >= MIN_REVIEWS else " Chưa đủ cỡ mẫu (cần ≥%d)." % MIN_REVIEWS))
        out += ["", "| Nhãn | Số review |", "|---|---:|"]
        out += ["| %s | %d |" % kv for kv in reviews["by_label"].items()]
        out += ["", "| App | Số chính / đã đọc |", "|---|---:|"]
        out += ["| %s | %d/%d |" % (app or "—", hit, total) for app, (hit, total) in sorted(reviews["by_app"].items())]
        out.append("")
        out.append("Người thứ hai gắn nhãn: %s" % ("khớp %d/%d" % reviews["agree"] if reviews["agree"]
                                                   else "[CHỜ DỮ LIỆU THẬT: evidence/reviews-check.csv]"))
        out += [""] + ["- \"%s\" — %s · %s · [nguồn](%s) · xem %s"
                       % (r["trich"], r["ma"], r["app"], r["link"], r["ngay_xem"]) for r in reviews["quotes"]]
    problems = interviews["problems"] + reviews["problems"]
    if problems:
        out += ["", "## Cần sửa trước khi dùng số"] + ["- " + p for p in problems]
    return "\n".join(out)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    reviews = count_reviews(os.path.join(HERE, "reviews.csv"), os.path.join(HERE, "reviews-check.csv"))
    print(report(reviews, count_interviews(os.path.join(HERE, "interviews"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
