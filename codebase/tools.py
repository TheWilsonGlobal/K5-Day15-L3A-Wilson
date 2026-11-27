"""Công cụ của bài toán E1 — giải thích chi tiêu từ sao kê (dữ liệu synthetic).

Mọi phép cộng, trừ, tỉ lệ nằm ở đây. Model không tính và không đọc được file đáp án.
Công cụ luôn đọc đúng một người dùng (CURRENT_USER): không công cụ nào nhận user_id làm tham số,
nên câu hỏi hay model không thể lấy được giao dịch của người khác.

Quy ước tên khoá (verify_numbers dựa vào đây): *_vnd là tiền · n_* là số đếm · *_pct là phần trăm.
"""

import contextlib
import csv
import datetime as dt
import json
import os
import re
import tempfile
import unicodedata

from tracing import tool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TX_PATH = os.path.join(ROOT, "data", "transactions.csv")
OVERRIDES_PATH = os.path.join(ROOT, "data", "overrides.json")

CURRENT_USER = "U001"
USE_OVERRIDES = False  # chỉ app.py bật; eval và simulate không đọc file sửa nhóm để chạy lại ra cùng kết quả

CATEGORIES = [
    "an_uong",
    "di_chuyen",
    "mua_sam",
    "hoa_don",
    "giai_tri",
    "suc_khoe",
    "giao_duc",
    "khong_ro",
]
LARGE_VND = 5000000  # khoản chi từ mức này được nêu riêng
DUPLICATE_MINUTES = 5  # hai khoản giống hệt trong khoảng này bị nêu "nghi trùng"

# Quy tắc nơi bán đã biết. CỐ Ý không phủ hết: phần còn lại là việc của model.
MERCHANT_RULES = {
    "bepmay": "an_uong",
    "timtim": "an_uong",
    "comcoba": "an_uong",
    "xemau": "di_chuyen",
    "songhong": "di_chuyen",
    "shopvui": "mua_sam",
    "xanhla": "mua_sam",
    "tiennha": "hoa_don",
    "tiendien": "hoa_don",
    "saobang": "hoa_don",
    "cinebox": "giai_tri",
}
_TRANSFER_WORDS = {
    "ck",
    "ct",
    "ibft",
    "mbvcb",
    "chuyen",
    "khoan",
    "tien",
    "den",
    "toi",
    "tk",
    "qua",
    "nhanh",
}
# Chữ chỉ nói "thanh toán một hoá đơn": không cho biết dịch vụ hay nơi bán.
_BILL_WORDS = {
    "thanh",
    "toan",
    "thanhtoan",
    "tt",
    "hoa",
    "don",
    "hoadon",
    "hd",
    "ma",
    "so",
}
# Từ chỉ loại hình đứng đầu tên nơi bán; sao kê thường không ghi. Giữ dấu để «quần áo» không bị coi là «quán».
_VENUE_PREFIX = re.compile(
    r"^\s*(?:quán|quan|tiệm|tiem|cửa\s+hàng|cua\s+hang|nhà\s+hàng|nha\s+hang|shop)\s+",
    re.IGNORECASE,
)
MIN_STRIPPED_KEY = 4  # phần tên còn lại ngắn hơn thì chỉ tìm theo tên đầy đủ


def fold(text):
    """Chữ thường, bỏ dấu tiếng Việt."""
    s = unicodedata.normalize("NFD", (text or "").lower().replace("đ", "d"))
    return "".join(c for c in s if not unicodedata.combining(c))


def compact(text):
    return re.sub(r"[^a-z0-9]", "", fold(text))


def description_key(text):
    """Khoá gộp các mô tả chỉ khác con số, để gửi model mỗi kiểu một lần."""
    return re.sub(r"[0-9]", "", compact(text))


def is_empty_transfer(description):
    """True khi mô tả chỉ gồm từ chuyển khoản, mã và số: không có nội dung để biết nhóm chi."""
    tokens = [t for t in re.split(r"[^a-z0-9]+", fold(description)) if t]
    if not any(t in _TRANSFER_WORDS or re.fullmatch(r"ft\d+", t) for t in tokens):
        return False
    return all(
        t in _TRANSFER_WORDS or t.isdigit() or re.fullmatch(r"ft\d+", t) for t in tokens
    )


def is_bare_bill_code(description):
    """True khi mô tả chỉ gồm chữ thanh toán / hoá đơn và mã số, không nêu dịch vụ hay nơi bán."""
    tokens = [t for t in re.split(r"[^a-z0-9]+", fold(description)) if t]
    codes = [bool(re.fullmatch(r"(?:hd)?\d+", t)) for t in tokens]
    if not all(code or t in _BILL_WORDS for t, code in zip(tokens, codes)):
        return False
    return any(t in ("hd", "hoadon") or re.fullmatch(r"hd\d+", t) for t in tokens) or {
        "hoa",
        "don",
    } <= set(tokens)


def _load():
    with open(TX_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["amount_vnd"] = int(r["amount_vnd"])
    return [r for r in rows if r["user_id"] == CURRENT_USER]


def _read_overrides():
    """Đọc data/overrides.json và kiểm từng nhóm. Nhóm lạ ném ValueError (không bỏ im lặng)."""
    with open(OVERRIDES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(
            "%s: phải là một object JSON, đang là %s"
            % (OVERRIDES_PATH, type(data).__name__)
        )
    for tx_id, category in data.items():
        if category not in CATEGORIES:
            raise ValueError(
                "%s: giao dịch %s có nhóm không hợp lệ %r"
                % (OVERRIDES_PATH, tx_id, category)
            )
    return data


def _overrides():
    if not USE_OVERRIDES or not os.path.exists(OVERRIDES_PATH):
        return {}
    return _read_overrides()


def _classify(tx, model_labels, overrides):
    """→ (kind, category, basis). basis: quy_tac · model · thieu_noi_dung · can_model · nguoi_dung."""
    key = compact(tx["description"])
    if tx["direction"] == "in":
        if "hoantien" in key:
            return "hoan_tien", "", "quy_tac"
        return ("thu_nhap" if "luong" in key else "tien_vao_khac"), "", "quy_tac"
    if "napvi" in key:
        return "nap_vi", "", "quy_tac"
    if "tietkiemcuatoi" in key or "tkcuatoi" in key:
        return "chuyen_noi_bo", "", "quy_tac"
    if tx["tx_id"] in overrides:
        return "chi", overrides[tx["tx_id"]], "nguoi_dung"
    for pattern, category in MERCHANT_RULES.items():
        if pattern in key:
            return "chi", category, "quy_tac"
    if is_empty_transfer(tx["description"]) or is_bare_bill_code(tx["description"]):
        return "chi", "khong_ro", "thieu_noi_dung"
    label = (model_labels or {}).get(description_key(tx["description"]))
    if label in CATEGORIES:
        return "chi", label, "model"
    return "chi", "khong_ro", "can_model"


@tool
def get_data_range() -> dict:
    """Khoảng ngày đang có dữ liệu.
    Input: không. Output: {"first", "last"} (YYYY-MM-DD). Không tác động ra ngoài."""
    dates = [r["date"] for r in _load()]
    return {"first": min(dates), "last": max(dates)}


@tool
def get_transactions(date_from: str, date_to: str) -> dict:
    """Giao dịch của người đang đăng nhập trong khoảng ngày (tính cả hai đầu).
    Input: date_from, date_to (YYYY-MM-DD). Output: {"transactions": [...], "n_tx"}. Không tác động ra ngoài."""
    dt.date.fromisoformat(date_from)
    dt.date.fromisoformat(date_to)
    rows = [r for r in _load() if date_from <= r["date"] <= date_to]
    return {"transactions": rows, "n_tx": len(rows)}


@tool
def categorize(transactions: list, model_labels: dict | None = None) -> list:
    """Gán loại và nhóm chi cho từng giao dịch: quy tắc trong code trước, nhãn của model cho phần còn lại.
    Input: danh sách giao dịch, {description_key: nhóm} (tuỳ chọn).
    Output: danh sách giao dịch thêm "kind", "category", "basis". Không tác động ra ngoài."""
    overrides = _overrides()
    out = []
    for tx in transactions:
        kind, category, basis = _classify(tx, model_labels, overrides)
        out.append(dict(tx, kind=kind, category=category, basis=basis))
    return out


def need_model(categorized):
    """Các kiểu mô tả mà quy tắc không gán được (mỗi kiểu một mục, thứ tự cố định)."""
    found = {}
    for tx in categorized:
        if tx["basis"] == "can_model":
            found.setdefault(description_key(tx["description"]), tx["description"])
    return [{"key": k, "description": found[k]} for k in sorted(found)]


def _minute_of(time_text):
    return int(time_text[:2]) * 60 + int(time_text[3:])


def _time_clusters(items):
    """Gom các khoản giống hệt theo giờ: hai khoản liền nhau cách không quá DUPLICATE_MINUTES thì cùng cụm.
    Cụm từ 2 khoản trở lên là nghi trùng; khoản cách xa mọi khoản khác không bị nêu."""
    ordered = sorted(items, key=lambda t: _minute_of(t["time"]))
    clusters = [[ordered[0]]]
    for prev, tx in zip(ordered, ordered[1:]):
        if _minute_of(tx["time"]) - _minute_of(prev["time"]) <= DUPLICATE_MINUTES:
            clusters[-1].append(tx)
        else:
            clusters.append([tx])
    return [c for c in clusters if len(c) >= 2]


def _duplicates(spend):
    groups = {}
    for tx in spend:
        groups.setdefault((tx["date"], tx["description"], tx["amount_vnd"]), []).append(
            tx
        )
    out = []
    for items in groups.values():
        for cluster in _time_clusters(items):
            out.append(sorted(cluster, key=lambda t: t["tx_id"]))
    return out


@tool
def sum_by_category(categorized: list) -> dict:
    """Tổng chi theo nhóm. Thu nhập, hoàn tiền, nạp ví, chuyển giữa tài khoản của mình không tính là chi.
    Input: danh sách giao dịch đã categorize.
    Output: tổng, từng nhóm, phần khong_ro, khoản hoàn tiền, khoản lớn, cặp nghi trùng, giao dịch chi.
    Không tác động ra ngoài."""
    spend = [t for t in categorized if t["kind"] == "chi"]
    refunds = [t for t in categorized if t["kind"] == "hoan_tien"]
    categories = []
    for c in CATEGORIES:
        items = [t for t in spend if t["category"] == c]
        if items:
            categories.append(
                {
                    "category": c,
                    "total_vnd": sum(t["amount_vnd"] for t in items),
                    "n_tx": len(items),
                }
            )
    categories.sort(key=lambda x: (-x["total_vnd"], x["category"]))
    unclear = [t for t in spend if t["category"] == "khong_ro"]
    large = [t for t in spend if t["amount_vnd"] >= LARGE_VND]
    duplicates = _duplicates(spend)
    return {
        "total_vnd": sum(t["amount_vnd"] for t in spend),
        "n_tx": len(spend),
        "categories": categories,
        "unclear_total_vnd": sum(t["amount_vnd"] for t in unclear),
        "n_unclear": len(unclear),
        "refund_total_vnd": sum(t["amount_vnd"] for t in refunds),
        "n_refunds": len(refunds),
        "large": large,
        "n_large": len(large),
        "duplicates": duplicates,
        "n_duplicate_groups": len(duplicates),
        "transactions": spend,
    }


def _change(a, b):
    diff = b - a
    return {
        "a_vnd": a,
        "b_vnd": b,
        "diff_abs_vnd": abs(diff),
        "direction": "tang" if diff > 0 else ("giam" if diff < 0 else "bang"),
        "change_pct": round(abs(diff) * 100.0 / a, 1) if a else None,
    }


@tool
def compare_months(summary_a: dict, summary_b: dict, partial: bool = False) -> dict:
    """So hai kết quả sum_by_category: chênh lệch từ a sang b, tổng và từng nhóm.
    Input: summary_a (mốc so), summary_b, partial (True khi so cùng kỳ vì một tháng chưa đủ ngày).
    Output: {"total", "categories", "partial"}. Không tác động ra ngoài."""
    a = {c["category"]: c["total_vnd"] for c in summary_a["categories"]}
    b = {c["category"]: c["total_vnd"] for c in summary_b["categories"]}
    cats = [
        dict(_change(a.get(c, 0), b.get(c, 0)), category=c)
        for c in CATEGORIES
        if c in a or c in b
    ]
    cats.sort(key=lambda x: (-x["diff_abs_vnd"], x["category"]))
    return {
        "total": _change(summary_a["total_vnd"], summary_b["total_vnd"]),
        "categories": cats,
        "partial": partial,
    }


def _merchant_keys(keyword):
    """Các khoá để so tên nơi bán: tên đầy đủ, và tên đã bỏ từ chỉ loại hình ở đầu («Quán …», «Tiệm …»)."""
    full = compact(keyword)
    rest = unicodedata.normalize("NFC", keyword or "")
    while found := _VENUE_PREFIX.match(rest):
        rest = rest[found.end() :]
    keys = [full] if len(full) >= 3 else []
    stripped = compact(rest)
    if stripped != full and len(stripped) >= MIN_STRIPPED_KEY:
        keys.append(stripped)
    return keys


@tool
def find_merchant(categorized: list, keyword: str) -> dict:
    """Khoản chi của một nơi bán, gộp các cách ghi (bỏ dấu, khoảng trắng, ký hiệu và từ chỉ loại hình ở đầu).
    Input: giao dịch đã categorize, từ khoá (ít nhất 3 chữ cái hoặc số).
    Output: {"transactions", "n_tx", "total_vnd"}. Không tác động ra ngoài."""
    keys = _merchant_keys(keyword)
    items = [
        t
        for t in categorized
        if t["kind"] == "chi" and any(k in compact(t["description"]) for k in keys)
    ]
    return {
        "transactions": items,
        "n_tx": len(items),
        "total_vnd": sum(t["amount_vnd"] for t in items),
    }


@tool
def propose_recategorize(tx_id: str, category: str) -> dict:
    """Soạn BẢN NHÁP đổi nhóm chi của một giao dịch. Không ghi gì; người dùng xác nhận thì app.py mới ghi.
    Input: tx_id, nhóm mới. Output: {"status": "ban_nhap" | "khong_hop_le", "tx", "new_category"}.
    Không tác động ra ngoài."""
    if category not in CATEGORIES:
        return {"status": "khong_hop_le", "tx": None, "new_category": category}
    for tx in _load():
        if tx["tx_id"] == tx_id:
            kind, old, basis = _classify(tx, None, _overrides())
            if kind != "chi":
                break
            return {
                "status": "ban_nhap",
                "tx": dict(tx, category=old, basis=basis),
                "new_category": category,
            }
    return {"status": "khong_hop_le", "tx": None, "new_category": category}


def apply_override(tx_id: str, category: str) -> None:
    """Ghi thay đổi người dùng ĐÃ XÁC NHẬN. Không phải công cụ của model: chỉ app.py gọi. Xoá file là hoàn tác."""
    if category not in CATEGORIES or tx_id not in {t["tx_id"] for t in _load()}:
        raise ValueError("giao dịch hoặc nhóm không hợp lệ")
    data = _read_overrides() if os.path.exists(OVERRIDES_PATH) else {}
    data[tx_id] = category
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    # Ghi vào file tạm cùng thư mục rồi đổi tên: lỗi giữa chừng không để lại file sửa dở.
    fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(OVERRIDES_PATH), prefix=".overrides-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, OVERRIDES_PATH)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.remove(tmp_path)
        raise
