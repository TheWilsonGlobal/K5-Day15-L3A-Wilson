"""Tải review công khai từ App Store Việt Nam theo đúng cách lấy mẫu ở evidence/data-mining.md §1a.

    python evidence/fetch_reviews.py                          tải mẫu → reviews.csv + fetch-log.json
    python evidence/fetch_reviews.py --dump <file ngoài repo> như trên, ghi thêm toàn văn (đã che) để gắn nhãn
    python evidence/fetch_reviews.py --refresh                tải lại khi reviews.csv đã có dòng (mẫu sẽ khác)
    python evidence/fetch_reviews.py --apply-labels evidence/labels-draft.csv
                                                              điền nhãn nháp, không gọi mạng

Không đọc và không lưu tên hay đường dẫn của người viết. Dòng người đã kiểm (human_verified = true)
giữ nguyên nhãn khi chạy lại. Chỉ dùng thư viện chuẩn.
"""
import csv
import datetime
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import count  # noqa: E402

REVIEWS = os.path.join(HERE, "reviews.csv")
LOG = os.path.join(HERE, "fetch-log.json")
APPS = [("MoMo", 918751511), ("Techcombank Mobile", 1548623362), ("Money Lover", 486312413)]
URL = "https://itunes.apple.com/vn/rss/customerreviews/page=%d/id=%d/sortBy=mostRecent/json"
STORE = "App Store VN"
PER_APP, MAX_PAGE, QUOTE_LIMIT = 50, 10, 500
USER_AGENT = "hackathon-prototype/1.0"

VI_MARKS = re.compile("[ăâđơưảạằắẳẵặầấẩẫậẻẽẹềếểễệỉịỏọồốổỗộờớởỡợủụừứửữựỳỷỹỵ]", re.I)
VI_PLAIN = {"khong", "ko", "duoc", "toi", "minh", "nhung", "dung", "tien", "rat", "chuyen", "loi", "nhap",
            "mong", "sao", "lai", "vay", "cua", "nay", "giao", "dich", "hang"}
KEYWORDS = ["giao dich", "lich su", "sao ke", "chi tieu", "thu chi", "thong ke", "bao cao", "phan loai",
            "tra cuu", "tim kiem", "so du", "tru tien"]


def is_vietnamese(text):
    text = unicodedata.normalize("NFC", text)
    return bool(VI_MARKS.search(text)) or len(set(re.findall(r"[a-z]+", text.lower())) & VI_PLAIN) >= 2


def has_words(text):
    return any(c.isalpha() for c in text)


def mask(text):
    """Che số điện thoại, số tài khoản, email, đường dẫn. Số tiền có dấu phân cách nghìn thì giữ."""
    text = re.sub(r"https?://\S+", "[đã che]", text)
    return count.PERSONAL.sub(lambda m: m.group(0) if count.AMOUNT.fullmatch(m.group(0)) else "[đã che]", text)


def quote(text):
    """Tối đa 2 câu liền nhau, từ câu đầu tiên có từ khoá; không có thì 2 câu đầu."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+|[\r\n]+", text) if has_words(s)]
    start = next((i for i, s in enumerate(sentences) if any(k in count.fold(s) for k in KEYWORDS)), 0)
    out = " ".join(sentences[start:start + 2])
    out = re.sub(r"\s+", " ", out)
    return out if len(out) <= QUOTE_LIMIT else out[:QUOTE_LIMIT].rsplit(" ", 1)[0] + " …"


def parse_entries(feed):
    """Chỉ lấy mã, ngày, số sao, tiêu đề, nội dung. Trường người viết không được đọc."""
    entries = feed.get("feed", {}).get("entry", [])
    if isinstance(entries, dict):
        entries = [entries]
    out = []
    for e in entries:
        if "im:rating" not in e:
            continue
        out.append({"id": e["id"]["label"], "date": e["updated"]["label"][:10], "rating": e["im:rating"]["label"],
                    "title": e.get("title", {}).get("label", ""), "content": e.get("content", {}).get("label", "")})
    return out


def fetch_page(app_id, page):
    request = urllib.request.Request(URL % (page, app_id), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return parse_entries(json.loads(response.read().decode("utf-8")))


def select(pages, limit=PER_APP):
    """pages: dãy (số trang, danh sách review). → (mẫu, số đếm). Áp dụng bước 2–5 của cách lấy mẫu."""
    chosen, seen = [], set()
    stats = {"pages": 0, "returned": 0, "duplicate": 0, "no_text": 0, "not_vietnamese": 0, "kept": 0}
    for page, items in pages:
        stats["pages"] += 1
        for item in items:
            if len(chosen) >= limit:
                break
            stats["returned"] += 1
            if item["id"] in seen:
                stats["duplicate"] += 1
                continue
            seen.add(item["id"])
            full = (item["title"] + "\n" + item["content"]).strip()
            if not has_words(item["content"]):
                stats["no_text"] += 1
            elif not is_vietnamese(full):
                stats["not_vietnamese"] += 1
            else:
                chosen.append(dict(item, page=page))
        if len(chosen) >= limit:
            break
    stats["kept"] = len(chosen)
    return chosen, stats


def pages_of(app_id, errors):
    for page in range(1, MAX_PAGE + 1):
        try:
            items = fetch_page(app_id, page)
        except Exception as e:  # ghi lại và dừng app này; không bịa thêm
            errors.append("trang %d: %s: %s" % (page, type(e).__name__, str(e)[:200]))
            return
        if not items:
            errors.append("trang %d: không trả review nào" % page)
            return
        yield page, items
        time.sleep(1)


def write(rows):
    with open(REVIEWS, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=count.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def fetch(dump=None, refresh=False):
    old = {r["ma"]: r for r in count.read_csv(REVIEWS)[1]}
    if old and not refresh:
        sys.exit("reviews.csv đã có %d dòng. Tải lại sẽ đổi mẫu; thêm --refresh nếu thật sự muốn." % len(old))
    today = datetime.date.today().isoformat()
    rows, log, full = [], {"fetched_at": datetime.datetime.now().isoformat(timespec="seconds"), "apps": []}, []
    for app, app_id in APPS:
        errors = []
        chosen, stats = select(pages_of(app_id, errors))
        log["apps"].append(dict(stats, app=app, app_id=app_id, errors=errors))
        print("%-20s giữ %d · trả về %d · trùng %d · không chữ %d · không phải tiếng Việt %d · %d trang%s" % (
            app, stats["kept"], stats["returned"], stats["duplicate"], stats["no_text"], stats["not_vietnamese"],
            stats["pages"], " · " + "; ".join(errors) if errors else ""))
        for item in chosen:
            row = {"ma": item["id"], "app": app, "kho": STORE, "link": URL % (item["page"], app_id),
                   "ngay_xem": today, "ngay_review": item["date"], "so_sao": item["rating"],
                   "trich": mask(quote(item["content"])), "nhan": "", "nguoi_gan": "", "human_verified": "false"}
            kept = old.get(item["id"])
            if kept and kept.get("human_verified", "").lower() == "true":
                row = {k: kept.get(k, "") for k in count.COLUMNS}
            rows.append(row)
            full.append({"ma": item["id"], "app": app, "so_sao": item["rating"],
                         "text": re.sub(r"\s+", " ", mask(item["title"] + " | " + item["content"]))})
    if not rows:
        sys.exit("Không lấy được review nào. Không ghi file.")
    write(rows)
    with open(LOG, "w", encoding="utf-8", newline="\n") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
        f.write("\n")
    if dump:
        with open(dump, "w", encoding="utf-8") as f:
            for item in full:
                f.write("%(ma)s [%(app)s %(so_sao)s sao] %(text)s\n" % item)
    print("Tổng %d review → evidence/reviews.csv" % len(rows))
    return 0


def apply_labels(path):
    """path: CSV cột ma,nhan,che — `che` là các chuỗi (tên người…) cần thay bằng [tên], cách nhau dấu ;"""
    drafts = {r["ma"].strip(): r for r in count.read_csv(path)[1]}
    rows = [{k: r.get(k, "") for k in count.COLUMNS} for r in count.read_csv(REVIEWS)[1]]
    unknown = sorted(set(drafts) - {r["ma"] for r in rows})
    bad = sorted({d["nhan"] for d in drafts.values()} - set(count.LABELS))
    if unknown or bad:
        sys.exit("Không ghi: mã không có trong reviews.csv %s · nhãn lạ %s" % (unknown[:5], bad))
    done = 0
    for row in rows:
        draft = drafts.get(row["ma"])
        if not draft or row["human_verified"].lower() == "true":
            continue
        row.update(nhan=draft["nhan"].strip(), nguoi_gan="Claude (nháp)", human_verified="false")
        for name in filter(None, (s.strip() for s in (draft.get("che") or "").split(";"))):
            row["trich"] = row["trich"].replace(name, "[tên]")
        done += 1
    write(rows)
    print("Đã điền nhãn nháp cho %d/%d dòng." % (done, len(rows)))
    return 0


def main(args):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if args[:1] == ["--apply-labels"] and len(args) == 2:
        return apply_labels(args[1])
    refresh = "--refresh" in args
    rest = [a for a in args if a != "--refresh"]
    if not rest:
        return fetch(refresh=refresh)
    if rest[0] == "--dump" and len(rest) == 2:
        return fetch(dump=rest[1], refresh=refresh)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
