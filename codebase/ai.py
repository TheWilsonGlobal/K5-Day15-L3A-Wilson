"""Nối model — chỗ DUY NHẤT trong bản chạy thử gọi model AI. NHÓM VIẾT phần gọi model thật.

Hợp đồng (giữ nguyên để khung đo được token):
    call_model(system: str, user: str) -> dict với 4 khoá
        "text":       str   chữ model trả về
        "model":      str   tên model đã gọi (để tra giá ở bảng giá model)
        "tokens_in":  int   số token vào, lấy từ trường usage trong phản hồi API — KHÔNG ước lượng
        "tokens_out": int   số token ra, gồm cả token suy luận / suy nghĩ nếu API tính riêng
    @model_call (từ tracing.py) tự ghi mỗi lần gọi vào trace; agent.py gọi call_model bao nhiêu lần
    cũng được, khung tự cộng token.
    Lỗi gọi model (hết lượt, sai key, mất mạng): cứ để exception bay ra — khung ghi lỗi vào cột error.

Chế độ giả (khi .env chưa có MODEL_PROVIDER, hoặc MODEL_PROVIDER=fake):
    trả một câu giả cố định, model "fake", token 0 — để luồng chạy hết khi chưa nối model.
    Lượt `run.py eval` / `run.py simulate` chạy bằng model giả KHÔNG được tính.

Model thật: điền .env (chép từ .env.example). Đã viết hai nhà cung cấp, chỉ dùng urllib:
    MODEL_PROVIDER=gemini   Gemini generateContent
    MODEL_PROVIDER=groq     Groq, API theo định dạng OpenAI
Gặp HTTP 429 thì đổi sang khoá tiếp theo trong API_KEYS. Không dán API key vào file này; thông báo lỗi
được xoá mọi chuỗi giống khoá trước khi ném ra (lỗi được ghi vào cột error và trace, là file sẽ commit).
"""

import json
import os
import re
import urllib.error
import urllib.request

from tracing import model_call

URL_GROQ = "https://api.groq.com/openai/v1/chat/completions"
URL_GEMINI = (
    "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"
)
USER_AGENT = "hackathon-prototype/1.0"  # User-Agent chung, không chứa thông tin cá nhân
TIMEOUT = 60
SHOW_RAW = False  # đổi thành True để in phản hồi của API khi cần tìm tên trường

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env(path=os.path.join(ROOT, ".env")):
    """Đọc file .env (KEY=VALUE mỗi dòng) vào biến môi trường, không ghi đè biến đã có. Khung — không cần sửa."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()
MODEL_PROVIDER = (os.environ.get("MODEL_PROVIDER") or "fake").strip().lower()
MODEL_NAME = (os.environ.get("MODEL_NAME") or "").strip()
API_KEY = (os.environ.get("API_KEY") or "").strip()
API_KEYS = list(
    dict.fromkeys(
        k.strip()
        for k in [API_KEY] + (os.environ.get("API_KEYS") or "").split(",")
        if k.strip()
    )
)
_key_index = (
    0  # khoá đang dùng; giữ giữa các lần gọi để không thử lại khoá vừa hết lượt
)
FAKE_PLAN = '{"intent": "nhieu_nhat", "from": "2026-11-01", "to": "2026-11-27"}'


class ModelError(RuntimeError):
    """Lỗi từ model hoặc đường truyền tới model (thiếu key, HTTP, mạng, phản hồi không có chữ hoặc thiếu token).
    app.py báo riêng loại này với lỗi cục bộ (dữ liệu, file sửa, mã trong codebase/)."""


def redact(text):
    """Xoá khoá khỏi chuỗi trước khi đưa vào thông báo lỗi. Khoá cũng được tìm ở dạng repr (vd ký tự xuống dòng
    bị escape thành \\n trong thông báo của ValueError) và ở dạng repr của bytes latin-1 (vd «é» thành \\xe9),
    vì các dạng đó không khớp chuỗi gốc."""
    for key in sorted(API_KEYS, key=len, reverse=True):
        for form in {
            key,
            repr(key)[1:-1],
            repr(key.encode("latin-1", "replace"))[2:-1],
        }:
            text = text.replace(form, "[khoá]")
    return re.sub(r"(?:gsk_|sk-|AIza|AQ\.)[A-Za-z0-9_\-.*]{6,}", "[khoá]", text)


def _post_with_keys(url, auth, payload):
    global _key_index
    for attempt in range(len(API_KEYS)):
        headers = dict(
            {"Content-Type": "application/json", "User-Agent": USER_AGENT},
            **auth(API_KEYS[_key_index % len(API_KEYS)]),
        )
        request = urllib.request.Request(
            url, data=payload, method="POST", headers=headers
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = redact(e.read().decode("utf-8", "replace"))[:300]
            if e.code == 429 and attempt + 1 < len(API_KEYS):
                _key_index += 1
                continue
            raise ModelError(
                "HTTP %d (đã thử %d khoá): %s" % (e.code, attempt + 1, detail)
            ) from None
        if not isinstance(data, dict):
            raise ModelError(
                "phản hồi không phải JSON object (%s)" % type(data).__name__
            )
        if SHOW_RAW:
            print(redact(json.dumps(data, ensure_ascii=False, indent=2))[:3000])
        return data


def post_json(url, auth, body):
    """POST JSON, trả JSON phản hồi. `auth(key)` trả header chứa khoá (khoá không nằm trong URL).
    Mọi lỗi thoát ra (HTTP, mạng, header, JSON hỏng) đều được ném lại dạng ModelError đã xoá khoá."""
    if not API_KEYS:
        raise ModelError("chưa có API_KEY trong .env")
    payload = json.dumps(body).encode("utf-8")
    try:
        return _post_with_keys(url, auth, payload)
    except ModelError:
        raise
    except Exception as e:
        raise ModelError("%s: %s" % (type(e).__name__, redact(str(e)))) from None


def _tokens(usage, key, provider):
    """Số token lấy đúng từ usage của API. Thiếu thì ném lỗi: không ước lượng và không coi là 0."""
    value = usage.get(key) if isinstance(usage, dict) else None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ModelError(
            "%s không trả %s trong usage — không ước lượng token" % (provider, key)
        )
    return value


def call_groq(system, user):
    data = post_json(
        URL_GROQ,
        lambda key: {"Authorization": "Bearer " + key},
        {
            "model": MODEL_NAME,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
    )
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ModelError("Groq không trả lựa chọn nào (choices rỗng hoặc sai dạng)")
    choice = choices[0]
    text = (choice.get("message") or {}).get("content")
    if not isinstance(text, str) or not text.strip():
        raise ModelError(
            "Groq không trả chữ (finish_reason=%s)"
            % (choice.get("finish_reason") or "không có")
        )
    usage = data.get("usage")
    return {
        "text": text,
        "tokens_in": _tokens(usage, "prompt_tokens", "Groq"),
        "tokens_out": _tokens(usage, "completion_tokens", "Groq"),
    }


def call_gemini(system, user):
    data = post_json(
        URL_GEMINI % MODEL_NAME,
        lambda key: {"x-goog-api-key": key},
        {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        },
    )
    candidates = data.get("candidates") or []
    candidate = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(
        p.get("text", "") for p in parts if isinstance(p, dict) and not p.get("thought")
    )
    if not text.strip():
        block = (data.get("promptFeedback") or {}).get("blockReason") or "không có"
        finish = candidate.get("finishReason") or "không có"
        raise ModelError(
            "Gemini không trả chữ (blockReason=%s, finishReason=%s)" % (block, finish)
        )
    usage = data.get("usageMetadata")
    return {
        "text": text,
        "tokens_in": _tokens(usage, "promptTokenCount", "Gemini"),
        "tokens_out": _tokens(usage, "candidatesTokenCount", "Gemini")
        + _thought_tokens(usage),
    }


def _thought_tokens(usage):
    """Token suy nghĩ tính tiền như token ra nên cộng vào. API không gửi trường này khi không có suy nghĩ (→ 0);
    đã gửi thì phải là số nguyên không âm, không phải bool, không phải số thực hay chuỗi."""
    if not isinstance(usage, dict) or "thoughtsTokenCount" not in usage:
        return 0
    value = usage["thoughtsTokenCount"]
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ModelError(
            "Gemini không trả thoughtsTokenCount hợp lệ (cần số nguyên không âm) — không ước lượng token"
        )
    return value


PROVIDERS = {"groq": call_groq, "gemini": call_gemini}


@model_call
def call_model(system: str, user: str) -> dict:
    if MODEL_PROVIDER == "fake":
        # Chế độ giả KHÔNG đọc câu hỏi: luôn trả một kế hoạch cố định (hoặc không gán nhãn nào),
        # chỉ để luồng đi hết. agent.py gắn thẻ [GIẢ] vào câu trả lời khi model == "fake".
        text = "{}" if system.startswith("NHIỆM VỤ: GÁN NHÓM CHI") else FAKE_PLAN
        return {"text": text, "model": "fake", "tokens_in": 0, "tokens_out": 0}
    if MODEL_PROVIDER not in PROVIDERS:
        raise NotImplementedError(
            "MODEL_PROVIDER=%s chưa được hỗ trợ trong codebase/ai.py (có: %s)"
            % (MODEL_PROVIDER, ", ".join(PROVIDERS))
        )
    r = PROVIDERS[MODEL_PROVIDER](system, user)
    return {
        "text": r["text"],
        "model": MODEL_NAME,
        "tokens_in": int(r["tokens_in"]),
        "tokens_out": int(r["tokens_out"]),
    }
