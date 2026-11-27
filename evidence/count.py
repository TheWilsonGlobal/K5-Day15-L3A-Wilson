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
COLUMNS = [
    "ma",
    "app",
    "kho",
    "link",
    "ngay_xem",
    "ngay_review",
    "so_sao",
    "trich",
    "nhan",
    "nguoi_gan",
    "human_verified",
]
MAIN = ["kho_hieu_gd", "kho_tong_hop", "kho_tim_gd"]  # tính vào số chính
SIDE = ["ngan_sach", "gd_bi_chan"]  # đếm riêng (hướng E2, E3)
LABELS = MAIN + SIDE + ["khac"]
MIN_REVIEWS, MIN_PEOPLE = 30, 3
PERSONAL = re.compile(r"\d[\d .-]{7,}\d|[\w.+-]+@[\w-]+\.\w+")
AMOUNT = re.compile(r"[1-9]\d{0,2}(?:[.,]\d{3})+")  # số tiền có dấu phân cách nghìn
PAIN = {"co": "co", "khong": "khong", "mot phan": "mot_phan", "mot_phan": "mot_phan"}
FIELDS = {
    "gap_pain": "Gặp pain",
    "so_lan_thang": "Số lần / 1 tháng qua",
    "so_phut": "Số phút lần gần nhất",
    "lan_gan_nhat": "Lần gần nhất",
    "xoay_xo": "Đang xoay xở bằng",
}


def fold(text):
    s = unicodedata.normalize("NFD", (text or "").strip().lower().replace("đ", "d"))
    return "".join(c for c in s if not unicodedata.combining(c))


def has_personal(text):
    return any(not AMOUNT.fullmatch(m.group(0)) for m in PERSONAL.finditer(text))


def read_csv(path):
    """→ (tên cột, dòng có chữ). Dòng thừa hoặc thiếu ô so với tiêu đề: csv.Error nêu số dòng, không đoán."""
    if not os.path.exists(path):
        return [], []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            if None in r or any(v is None for v in r.values()):
                raise csv.Error(
                    "dòng %d có số ô khác tiêu đề (%d cột)"
                    % (reader.line_num, len(reader.fieldnames or []))
                )
            if any((v or "").strip() for v in r.values()):
                rows.append(r)
        return reader.fieldnames or [], rows


def count_reviews(path, check_path=None):
    """→ dict kết quả đếm review. `errors` khác rỗng: file không đếm được, báo lỗi và không in x/N."""
    errors, fields, rows = [], [], []
    if not os.path.exists(path):
        errors.append(
            "không thấy %s: file phải có sẵn (ít nhất một dòng tiêu đề)" % path
        )
    else:
        try:
            fields, rows = read_csv(path)
        except (OSError, UnicodeError, csv.Error) as e:
            errors.append("không đọc được reviews.csv: %s" % e)
        else:
            if fields != COLUMNS:
                errors.append(
                    "reviews.csv phải có đúng các cột: %s" % ",".join(COLUMNS)
                )
                rows = []
    problems = []
    clean = [{k: (r.get(k) or "").strip() for k in COLUMNS} for r in rows]
    codes = [r["ma"] for r in clean]
    for code in sorted({c for c in codes if codes.count(c) > 1 or not c}):
        errors.append("mã review trống hoặc trùng: %r" % code)
    for r in clean:
        if not r["nhan"]:
            problems.append("%s chưa gắn nhãn" % r["ma"])
        elif r["nhan"] not in LABELS:
            problems.append("%s có nhãn lạ: %s" % (r["ma"], r["nhan"]))
        for column in ("link", "ngay_xem", "trich"):
            if not r[column]:
                problems.append("%s thiếu cột %s" % (r["ma"], column))
        if has_personal(r["trich"]):
            problems.append(
                "%s: trích dẫn có chuỗi giống số điện thoại / tài khoản / email, che trước khi commit"
                % r["ma"]
            )
    labelled = [r for r in clean if r["nhan"] in LABELS]
    checked = [r for r in labelled if r["human_verified"].lower() == "true"]
    agree = None
    if check_path and os.path.exists(check_path):
        agree = check_agreement(check_path, labelled, errors)
    result = {
        "verified": len(checked),
        "main_verified": sum(r["nhan"] in MAIN for r in checked),
        "n": len(clean),
        "labelled": len(labelled),
        "problems": problems,
        "errors": errors,
        "main": sum(r["nhan"] in MAIN for r in labelled),
        "by_label": {
            label: sum(r["nhan"] == label for r in labelled) for label in LABELS
        },
        "by_app": {},
        "quotes": [r for r in labelled if r["nhan"] in MAIN],
        "agree": agree,
    }
    for r in labelled:
        hit, n = result["by_app"].get(r["app"], (0, 0))
        result["by_app"][r["app"]] = (hit + (r["nhan"] in MAIN), n + 1)
    return result


def check_agreement(check_path, labelled, errors):
    """reviews-check.csv (người thứ hai): → (khớp, số cặp) hoặc None. File có mà không đọc được, hoặc thiếu ma,nhan: ghi lỗi."""
    try:
        fields, rows = read_csv(check_path)
    except (OSError, UnicodeError, csv.Error) as e:
        errors.append("không đọc được reviews-check.csv: %s" % e)
        return None
    if not {"ma", "nhan"} <= set(fields):
        errors.append(
            "reviews-check.csv phải có tiêu đề cột ma,nhan (đang có: %s)"
            % (",".join(fields) or "trống")
        )
        return None
    second = {(r.get("ma") or "").strip(): (r.get("nhan") or "").strip() for r in rows}
    pairs = [(r["nhan"], second[r["ma"]]) for r in labelled if second.get(r["ma"])]
    return (sum(a == b for a, b in pairs), len(pairs))


def _field(text, label):
    m = re.search(
        r"(?im)^[ \t]*[-*][ \t]*%s[ \t]*:[ \t]*(.*)$" % re.escape(label), text
    )
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
    quotes = (
        re.findall(r"(?m)^[ \t]*[-*][ \t]*[\"“](.+?)[\"”]", section.group(1))
        if section
        else []
    )
    person["quotes"] = [q.strip() for q in quotes if q.strip() not in ("", "…", "...")]
    person["personal"] = has_personal(text.split("\n", 1)[-1])
    return person


def count_interviews(folder):
    """Mỗi file P*.md một người. File không đọc được (sai mã hoá, là thư mục…) → errors, không đếm, không kết luận."""
    people, errors = [], []
    for p in sorted(glob.glob(os.path.join(folder, "P*.md"))):
        if not re.fullmatch(r"P\d+\.md", os.path.basename(p)):
            continue
        try:
            people.append(read_interview(p))
        except (OSError, UnicodeError) as e:
            errors.append("không đọc được %s: %s" % (os.path.basename(p), e))
    problems = []
    for p in people:
        if not p["vai"]:
            problems.append("%s: dòng tiêu đề chưa ghi vai" % p["ma"])
        if not p["gap_pain"]:
            problems.append('%s: chưa ghi "Gặp pain: co / khong / mot phan"' % p["ma"])
        if not p["quotes"]:
            problems.append("%s: chưa có trích nguyên văn" % p["ma"])
        if p["personal"]:
            problems.append(
                "%s: có chuỗi giống số điện thoại / tài khoản / email" % p["ma"]
            )
    n = len(people)
    x = sum(p["gap_pain"] == "co" for p in people)
    if n < MIN_PEOPLE:
        verdict = "chưa đủ người (cần ≥%d)" % MIN_PEOPLE
    elif any(not p["gap_pain"] for p in people):
        verdict = 'chưa kết luận: còn file chưa ghi "Gặp pain"'
    elif x >= 3 and x * 4 >= 3 * n:
        verdict = "ĐẠT ngưỡng giả thuyết (≥3 người và ≥75%)"
    elif x < 2:
        verdict = "giả thuyết SAI (dưới 2 người kể được) → xem evidence/hypothesis.md"
    else:
        verdict = "chưa đạt ngưỡng giả thuyết"
    if errors:
        verdict = "không kết luận: có file phỏng vấn không đọc được"
    return {
        "n": n,
        "x": x,
        "partial": sum(p["gap_pain"] == "mot_phan" for p in people),
        "people": people,
        "problems": problems,
        "verdict": verdict,
        "errors": errors,
    }


def report(reviews, interviews):
    out = ["# Đếm bằng chứng (python evidence/count.py)", "", "## Phỏng vấn"]
    if interviews["errors"]:
        out += ["- LỖI: %s" % e for e in interviews["errors"]]
        out.append(
            "Không đếm người và không kết luận giả thuyết: có file phỏng vấn không đọc được. Sửa lỗi rồi chạy lại."
        )
    elif not interviews["n"]:
        out.append("[CHỜ DỮ LIỆU THẬT: chưa có file evidence/interviews/P*.md]")
    else:
        out += [
            "",
            "**%d/%d người** kể được một lần cụ thể (một phần: %d). Kết luận: %s."
            % (
                interviews["x"],
                interviews["n"],
                interviews["partial"],
                interviews["verdict"],
            ),
            "",
            "| Mã | Vai | " + " | ".join(FIELDS.values()) + " |",
            "|---|---|" + "---|" * len(FIELDS),
        ]
        for p in interviews["people"]:
            out.append(
                "| %s | %s | %s |"
                % (p["ma"], p["vai"] or "—", " | ".join(p[k] or "—" for k in FIELDS))
            )
        out += [""] + [
            '- "%s" — %s (%s)' % (q, p["ma"], p["vai"] or "chưa ghi vai")
            for p in interviews["people"]
            for q in p["quotes"]
        ]
    out += ["", "## Review công khai"]
    n = reviews["n"]
    if reviews["errors"]:
        out += ["- LỖI: %s" % e for e in reviews["errors"]]
        out.append(
            "Không in x/N cho review: file không đếm được. Sửa lỗi rồi chạy lại."
        )
    elif not n:
        out.append("[CHỜ DỮ LIỆU THẬT: evidence/reviews.csv chưa có dòng nào]")
    elif reviews["labelled"] < n:
        out.append("Mới gắn nhãn %d/%d dòng: chưa tính x/N." % (reviews["labelled"], n))
    else:
        out.append("")
        draft = reviews["verified"] < n
        if draft:
            out += [
                "**NHÁP, CHƯA PHẢI BẰNG CHỨNG:** người mới kiểm %d/%d dòng (trong đó %d thuộc 3 nhãn chính). "
                "Số dưới đây theo nhãn chưa kiểm hết."
                % (reviews["verified"], n, reviews["main_verified"]),
                "",
            ]
        out.append(
            "**%d/%d review (%.0f%%)** kể khó khăn khi xem, hiểu hoặc tổng hợp giao dịch%s.%s"
            % (
                reviews["main"],
                n,
                100.0 * reviews["main"] / n,
                " (nhãn nháp)" if draft else "",
                "" if n >= MIN_REVIEWS else " Chưa đủ cỡ mẫu (cần ≥%d)." % MIN_REVIEWS,
            )
        )
        out += ["", "| Nhãn | Số review |", "|---|---:|"]
        out += ["| %s | %d |" % kv for kv in reviews["by_label"].items()]
        out += ["", "| App | Số chính / đã đọc |", "|---|---:|"]
        out += [
            "| %s | %d/%d |" % (app or "—", hit, total)
            for app, (hit, total) in sorted(reviews["by_app"].items())
        ]
        out.append("")
        out.append(
            "Người thứ hai gắn nhãn: %s"
            % (
                "khớp %d/%d" % reviews["agree"]
                if reviews["agree"] and reviews["agree"][1]
                else "[CHỜ DỮ LIỆU THẬT: evidence/reviews-check.csv]"
            )
        )
        out += [""] + [
            '- "%s" — %s · %s · [nguồn](%s) · xem %s'
            % (r["trich"], r["ma"], r["app"], r["link"], r["ngay_xem"])
            for r in reviews["quotes"]
        ]
    problems = interviews["problems"] + reviews["problems"]
    if problems:
        out += ["", "## Cần sửa trước khi dùng số"] + ["- " + p for p in problems]
    return "\n".join(out)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    reviews = count_reviews(
        os.path.join(HERE, "reviews.csv"), os.path.join(HERE, "reviews-check.csv")
    )
    interviews = count_interviews(os.path.join(HERE, "interviews"))
    print(report(reviews, interviews))
    return 1 if reviews["errors"] or interviews["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
