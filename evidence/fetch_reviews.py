"""Tải review công khai từ App Store Việt Nam theo đúng cách lấy mẫu ở evidence/data-mining.md §1a.

    python evidence/fetch_reviews.py                          tải mẫu → reviews.csv + fetch-log.json
    python evidence/fetch_reviews.py --dump <file ngoài repo> như trên, ghi thêm toàn văn (đã che) để gắn nhãn
    python evidence/fetch_reviews.py --refresh                tải lại khi reviews.csv đã có dòng (mẫu sẽ khác)
    python evidence/fetch_reviews.py --refresh --allow-partial
                                                              khi có app lỗi: vẫn ghi mẫu từng phần, thoát 0;
                                                              fetch-log.json ghi các app lỗi (failed_apps)
    python evidence/fetch_reviews.py --apply-labels evidence/labels-draft.csv
                                                              điền nhãn nháp, không gọi mạng

Quy tắc lỗi (không bao giờ ghi file dở dang):
  - mọi app đều lỗi: in từng lỗi, không ghi file nào, thoát 1.
  - một phần app lỗi, không có --allow-partial: cảnh báo liệt kê app lỗi, không ghi file nào, thoát 1.
  - một phần app lỗi, có --allow-partial: cảnh báo, ghi mẫu từng phần, thoát 0.
  - app lỗi không đóng góp mẫu mới: dòng nháp (chưa kiểm) của app đó không còn trong reviews.csv;
    dòng đã kiểm luôn được giữ.
  - --dump không được trỏ vào trong repo (file chứa toàn văn review), thoát 1.
  - trang 1 của app trả rỗng hoặc lỗi mạng: lỗi của app. Thân JSON không có object "feed" ở bất kỳ trang nào:
    lỗi của app (CR3-09). Trang sau trang 1 có object feed nhưng không có review là HẾT FEED (quyết định PM
    27/11, CR2-08): giữ các review đã tải của app đó, không tính là lỗi.
  - reviews.csv có dòng thừa hoặc thiếu ô so với tiêu đề: dừng, nêu số dòng, không ghi gì (cả --refresh lẫn --apply-labels).
  - mọi file đầu ra (--dump, reviews.csv, fetch-log.json) được ghi file tạm trước; chỉ khi mọi file tạm đã ghi xong
    mới đổi tên. Ghi tạm lỗi thì không file đích nào đổi. Đổi tên lỗi giữa chừng thì thông báo file nào đã đổi.

Không đọc và không lưu tên hay đường dẫn của người viết. Dòng người đã kiểm (human_verified = true)
giữ nguyên nhãn khi chạy lại, kể cả khi không nằm trong mẫu mới hoặc app của nó bị lỗi. Chỉ dùng thư viện chuẩn.
"""

import csv
import datetime
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import count  # noqa: E402 — phải thêm HERE vào sys.path trước khi import, nên không đứng đầu file được.

REVIEWS = os.path.join(HERE, "reviews.csv")
LOG = os.path.join(HERE, "fetch-log.json")
APPS = [
    ("MoMo", 918751511),
    ("Techcombank Mobile", 1548623362),
    ("Money Lover", 486312413),
]
URL = "https://itunes.apple.com/vn/rss/customerreviews/page=%d/id=%d/sortBy=mostRecent/json"
STORE = "App Store VN"
PER_APP, MAX_PAGE, QUOTE_LIMIT = 50, 10, 500
USER_AGENT = "hackathon-prototype/1.0"

VI_MARKS = re.compile("[ăâđơưảạằắẳẵặầấẩẫậẻẽẹềếểễệỉịỏọồốổỗộờớởỡợủụừứửữựỳỷỹỵ]", re.I)
VI_PLAIN = {
    "khong",
    "ko",
    "duoc",
    "toi",
    "minh",
    "nhung",
    "dung",
    "tien",
    "rat",
    "chuyen",
    "loi",
    "nhap",
    "mong",
    "sao",
    "lai",
    "vay",
    "cua",
    "nay",
    "giao",
    "dich",
    "hang",
}
KEYWORDS = [
    "giao dich",
    "lich su",
    "sao ke",
    "chi tieu",
    "thu chi",
    "thong ke",
    "bao cao",
    "phan loai",
    "tra cuu",
    "tim kiem",
    "so du",
    "tru tien",
]


class Loi(Exception):
    """Lỗi làm dừng lệnh. Lệnh in thông báo rồi thoát 1, và không ghi file nào dở dang."""


def is_vietnamese(text):
    text = unicodedata.normalize("NFC", text)
    return (
        bool(VI_MARKS.search(text))
        or len(set(re.findall(r"[a-z]+", text.lower())) & VI_PLAIN) >= 2
    )


def has_words(text):
    return any(c.isalpha() for c in text)


def mask(text):
    """Che số điện thoại, số tài khoản, email, đường dẫn. Số tiền có dấu phân cách nghìn thì giữ."""
    text = re.sub(r"https?://\S+", "[đã che]", text)
    return count.PERSONAL.sub(
        lambda m: m.group(0) if count.AMOUNT.fullmatch(m.group(0)) else "[đã che]", text
    )


def quote(text):
    """Tối đa 2 câu liền nhau, từ câu đầu tiên có từ khoá; không có thì 2 câu đầu."""
    sentences = [
        s.strip() for s in re.split(r"(?<=[.!?…])\s+|[\r\n]+", text) if has_words(s)
    ]
    start = next(
        (
            i
            for i, s in enumerate(sentences)
            if any(k in count.fold(s) for k in KEYWORDS)
        ),
        0,
    )
    out = " ".join(sentences[start : start + 2])
    out = re.sub(r"\s+", " ", out)
    return (
        out if len(out) <= QUOTE_LIMIT else out[:QUOTE_LIMIT].rsplit(" ", 1)[0] + " …"
    )


def parse_entries(body):
    """Chỉ lấy mã, ngày, số sao, tiêu đề, nội dung. Trường người viết không được đọc.
    Thân JSON không có object "feed" (ví dụ {} hoặc {"error": …}) là lỗi của app, không phải trang rỗng (CR3-09)."""
    feed = body.get("feed") if isinstance(body, dict) else None
    if not isinstance(feed, dict):
        raise ValueError("phản hồi không có object 'feed'")
    entries = feed.get("entry", [])
    if isinstance(entries, dict):
        entries = [entries]
    out = []
    for e in entries:
        if "im:rating" not in e:
            continue
        out.append(
            {
                "id": e["id"]["label"],
                "date": e["updated"]["label"][:10],
                "rating": e["im:rating"]["label"],
                "title": e.get("title", {}).get("label", ""),
                "content": e.get("content", {}).get("label", ""),
            }
        )
    return out


def fetch_page(app_id, page):
    request = urllib.request.Request(
        URL % (page, app_id), headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return parse_entries(json.loads(response.read().decode("utf-8")))


def select(pages, limit=PER_APP):
    """pages: dãy (số trang, danh sách review). → (mẫu, số đếm). Áp dụng bước 2–5 của cách lấy mẫu."""
    chosen, seen = [], set()
    stats = {
        "pages": 0,
        "returned": 0,
        "duplicate": 0,
        "no_text": 0,
        "not_vietnamese": 0,
        "kept": 0,
    }
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
            if page == 1:
                errors.append("trang 1: không trả review nào")
            return  # trang sau trang 1 rỗng (có object feed, không entry): hết feed, không phải lỗi (PM 27/11)
        yield page, items
        time.sleep(1)


def write_files(files):
    """files: [(đường dẫn đích, nội dung, mã hoá)]. Ghi mọi file tạm trước; chỉ khi tất cả đã ghi xong mới đổi tên.
    Ghi tạm lỗi → không file đích nào đổi. Đổi tên lỗi giữa chừng → báo file nào đã đổi, file nào chưa."""
    try:
        for path, text, encoding in files:
            try:
                with open(path + ".tmp", "w", encoding=encoding, newline="") as f:
                    f.write(text)
            except (
                OSError,
                UnicodeError,
            ) as e:  # UnicodeError: ví dụ surrogate lẻ trong nội dung review
                raise Loi("không ghi được %s: %s. Không file nào bị đổi." % (path, e))
        done = []
        for path, _, _ in files:
            try:
                os.replace(path + ".tmp", path)
            except OSError as e:
                rest = [p for p, _, _ in files if p not in done and p != path]
                raise Loi(
                    "không ghi được %s: %s. Đã đổi: %s. Chưa đổi: %s."
                    % (
                        path,
                        e,
                        ", ".join(done) or "không file nào",
                        ", ".join([path] + rest),
                    )
                )
            done.append(path)
    finally:
        _remove_temps(
            files
        )  # mọi lối thoát, kể cả ngoại lệ không lường trước: không để file tạm sót lại


def _remove_temps(files):
    for path, _, _ in files:
        tmp = path + ".tmp"
        if os.path.exists(tmp):
            os.remove(tmp)


def csv_text(rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=count.COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def is_verified(row):
    return (row.get("human_verified") or "").strip().lower() == "true"


def read_reviews():
    """Dòng của reviews.csv; chưa có file thì rỗng. Không đọc được hoặc sai cột thì dừng, không đoán."""
    if not os.path.exists(REVIEWS):
        return []
    try:
        fields, rows = count.read_csv(REVIEWS)
    except (OSError, UnicodeError, csv.Error) as e:
        raise Loi("không đọc được reviews.csv: %s" % e)
    if fields != count.COLUMNS:
        raise Loi("reviews.csv phải có đúng các cột: %s" % ",".join(count.COLUMNS))
    return rows


def read_drafts(path):
    """File nhãn nháp, cột ma,nhan,che. → {mã: {nhan, che}}. Sai cột, mã trống hoặc trùng thì dừng."""
    try:
        fields, rows = count.read_csv(path)
    except (OSError, UnicodeError, csv.Error) as e:
        raise Loi("không đọc được file nhãn nháp %s: %s" % (path, e))
    missing = [c for c in ("ma", "nhan", "che") if c not in fields]
    if missing:
        raise Loi("file nhãn nháp thiếu cột: %s" % ",".join(missing))
    drafts = {}
    for r in rows:
        code = (r.get("ma") or "").strip()
        if not code:
            raise Loi("file nhãn nháp có dòng không có mã")
        if code in drafts:
            raise Loi("file nhãn nháp có mã trùng: %s" % code)
        drafts[code] = {
            "nhan": (r.get("nhan") or "").strip(),
            "che": r.get("che") or "",
        }
    return drafts


def _plain(path):
    """Bỏ tiền tố \\\\?\\ (và \\\\?\\UNC\\) mà đường dẫn giải trên Windows có thể mang theo."""
    if path.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path[8:]
    if path.startswith("\\\\?\\"):
        return path[4:]
    return path


def in_repo(path):
    """Đường dẫn có nằm trong repo không. Hai cách, cách nào khớp cũng là trong repo:
    so đường dẫn đã giải (bỏ \\\\?\\); rồi so file thật với từng thư mục cha, để \\\\localhost\\c$\\… cũng bị chặn."""
    root = _plain(os.path.realpath(ROOT))
    target = _plain(os.path.realpath(path))
    try:
        if os.path.commonpath(
            [os.path.normcase(target), os.path.normcase(root)]
        ) == os.path.normcase(root):
            return True
    except (
        ValueError
    ):  # khác ổ đĩa hoặc khác kiểu (UNC / ổ): để việc so file thật quyết định
        pass
    probe = os.path.abspath(path)
    while True:
        if os.path.exists(probe) and os.path.samefile(probe, ROOT):
            return True
        parent = os.path.dirname(probe)
        if parent == probe:
            return False
        probe = parent


def check_dump(path):
    try:
        inside = in_repo(path)
    except OSError as e:
        raise Loi("không kiểm tra được --dump %s: %s. Không ghi gì." % (path, e))
    if inside:
        raise Loi(
            "--dump không được ghi vào trong repo (%s): file đó chứa toàn văn review. Chọn thư mục ngoài repo."
            % ROOT
        )
    if os.path.isdir(path):
        raise Loi("--dump trỏ vào một thư mục: %s" % path)


def fetch(dump=None, refresh=False, allow_partial=False):
    if dump:
        check_dump(dump)
    old_rows = read_reviews()
    if old_rows and not refresh:
        raise Loi(
            "reviews.csv đã có %d dòng. Tải lại sẽ đổi mẫu; thêm --refresh nếu thật sự muốn."
            % len(old_rows)
        )
    today = datetime.date.today().isoformat()
    # Dòng đã kiểm, theo mã, giữ nguyên từng dòng (kể cả khi trùng mã). Không bao giờ bỏ rơi dòng nào.
    human = {}
    for r in old_rows:
        if is_verified(r):
            human.setdefault((r.get("ma") or "").strip(), []).append(
                {k: r.get(k, "") for k in count.COLUMNS}
            )
    log = {
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "allow_partial": allow_partial,
        "apps": [],
    }
    results = []
    for app, app_id in APPS:
        errors = []
        chosen, stats = select(pages_of(app_id, errors))
        log["apps"].append(dict(stats, app=app, app_id=app_id, errors=errors))
        print(
            "%-20s giữ %d · trả về %d · trùng %d · không chữ %d · không phải tiếng Việt %d · %d trang%s"
            % (
                app,
                stats["kept"],
                stats["returned"],
                stats["duplicate"],
                stats["no_text"],
                stats["not_vietnamese"],
                stats["pages"],
                " · " + "; ".join(errors) if errors else "",
            )
        )
        results.append((app, app_id, chosen, errors))
    failed = [a["app"] for a in log["apps"] if a["errors"]]
    log["failed_apps"] = failed
    log["partial"] = bool(failed)
    if len(failed) == len(APPS):
        for a in log["apps"]:
            for e in a["errors"]:
                print("LỖI %s: %s" % (a["app"], e))
        raise Loi("mọi app đều lỗi. Không ghi file nào.")
    if failed:
        print("CẢNH BÁO: app lỗi: %s." % ", ".join(failed))
        if not allow_partial:
            raise Loi(
                "không ghi file nào. Thêm --allow-partial để ghi mẫu từng phần "
                "(thoát 0, fetch-log.json ghi app lỗi)."
            )
        print("CẢNH BÁO: --allow-partial: ghi mẫu TỪNG PHẦN, thiếu các app trên.")
    rows, full, emitted = [], [], set()
    for app, app_id, chosen, errors in results:
        if errors:
            continue  # app lỗi không đóng góp mẫu mới; dòng đã kiểm của nó được giữ ở cuối
        for item in chosen:
            code = item["id"]
            if code in human:
                if code not in emitted:
                    rows.extend(human[code])
                    emitted.add(code)
            else:
                rows.append(
                    {
                        "ma": code,
                        "app": app,
                        "kho": STORE,
                        "link": URL % (item["page"], app_id),
                        "ngay_xem": today,
                        "ngay_review": item["date"],
                        "so_sao": item["rating"],
                        "trich": mask(quote(item["content"])),
                        "nhan": "",
                        "nguoi_gan": "",
                        "human_verified": "false",
                    }
                )
            full.append(
                {
                    "ma": code,
                    "app": app,
                    "so_sao": item["rating"],
                    "text": re.sub(
                        r"\s+", " ", mask(item["title"] + " | " + item["content"])
                    ),
                }
            )
    for code, group in human.items():
        if code not in emitted:
            rows.extend(group)
    if not rows:
        raise Loi("Không lấy được review nào. Không ghi file.")
    files = [
        (REVIEWS, csv_text(rows), "utf-8-sig"),
        (LOG, json.dumps(log, ensure_ascii=False, indent=2) + "\n", "utf-8"),
    ]
    if dump:
        files.insert(
            0,
            (
                dump,
                "".join(
                    "%(ma)s [%(app)s %(so_sao)s sao] %(text)s\n" % item for item in full
                ),
                "utf-8",
            ),
        )
    write_files(files)
    print(
        "Tổng %d review → evidence/reviews.csv%s"
        % (len(rows), " (THIẾU app: %s)" % ", ".join(failed) if failed else "")
    )
    return 0


def apply_labels(path):
    """path: CSV cột ma,nhan,che — `che` là các chuỗi (tên người…) cần thay bằng [tên], cách nhau dấu ;"""
    if not os.path.isfile(path):
        raise Loi("không thấy file nhãn nháp: %s. Không ghi reviews.csv." % path)
    if not os.path.exists(REVIEWS):
        raise Loi("không thấy reviews.csv. Không ghi gì.")
    drafts = read_drafts(path)
    rows = [{k: r.get(k, "") for k in count.COLUMNS} for r in read_reviews()]
    codes = [(r["ma"] or "").strip() for r in rows]
    dup = sorted({c for c in codes if codes.count(c) > 1})
    if dup:
        raise Loi("reviews.csv có mã trùng %s. Không ghi." % dup[:5])
    unknown = sorted(set(drafts) - set(codes))
    bad = sorted({d["nhan"] for d in drafts.values()} - set(count.LABELS))
    if unknown or bad:
        raise Loi(
            "Không ghi: mã không có trong reviews.csv %s · nhãn lạ %s"
            % (unknown[:5], bad)
        )
    done = 0
    for row in rows:
        draft = drafts.get((row["ma"] or "").strip())
        if not draft or is_verified(row):
            continue
        row.update(
            nhan=draft["nhan"], nguoi_gan="Claude (nháp)", human_verified="false"
        )
        for name in filter(None, (s.strip() for s in draft["che"].split(";"))):
            row["trich"] = (row["trich"] or "").replace(name, "[tên]")
        done += 1
    write_files([(REVIEWS, csv_text(rows), "utf-8-sig")])
    print("Đã điền nhãn nháp cho %d/%d dòng." % (done, len(rows)))
    return 0


def run(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Loi as e:
        print("LỖI: %s" % e)
        return 1


def main(args):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if args[:1] == ["--apply-labels"] and len(args) == 2:
        return run(apply_labels, args[1])
    refresh = "--refresh" in args
    allow_partial = "--allow-partial" in args
    rest = [a for a in args if a not in ("--refresh", "--allow-partial")]
    if not rest:
        return run(fetch, refresh=refresh, allow_partial=allow_partial)
    if rest[0] == "--dump" and len(rest) == 2:
        return run(fetch, dump=rest[1], refresh=refresh, allow_partial=allow_partial)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
