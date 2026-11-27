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
URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"
USER_AGENT = "hackathon-prototype/1.0"   # User-Agent chung, không chứa thông tin cá nhân
TIMEOUT = 60
SHOW_RAW = False   # đổi thành True để in phản hồi của API khi cần tìm tên trường

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
API_KEYS = list(dict.fromkeys(
    k.strip() for k in [API_KEY] + (os.environ.get("API_KEYS") or "").split(",") if k.strip()))
_key_index = 0   # khoá đang dùng; giữ giữa các lần gọi để không thử lại khoá vừa hết lượt
FAKE_PLAN = '{"intent": "nhieu_nhat", "from": "2026-11-01", "to": "2026-11-27"}'


def redact(text):
    """Xoá khoá khỏi chuỗi trước khi đưa vào thông báo lỗi."""
    for key in API_KEYS:
        text = text.replace(key, "[khoá]")
    return re.sub(r"(?:gsk_|sk-|AIza|AQ\.)[A-Za-z0-9_\-.*]{6,}", "[khoá]", text)


def post_json(url, auth, body):
    """POST JSON, trả JSON phản hồi. `auth(key)` trả header chứa khoá (khoá không nằm trong URL)."""
    global _key_index
    if not API_KEYS:
        raise RuntimeError("chưa có API_KEY trong .env")
    payload = json.dumps(body).encode("utf-8")
    for attempt in range(len(API_KEYS)):
        headers = dict({"Content-Type": "application/json", "User-Agent": USER_AGENT},
                       **auth(API_KEYS[_key_index % len(API_KEYS)]))
        request = urllib.request.Request(url, data=payload, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = redact(e.read().decode("utf-8", "replace"))[:300]
            if e.code == 429 and attempt + 1 < len(API_KEYS):
                _key_index += 1
                continue
            raise RuntimeError("HTTP %d (đã thử %d khoá): %s" % (e.code, attempt + 1, detail)) from None
        if SHOW_RAW:
            print(redact(json.dumps(data, ensure_ascii=False, indent=2))[:3000])
        return data


def call_groq(system, user):
    data = post_json(URL_GROQ, lambda key: {"Authorization": "Bearer " + key},
                     {"model": MODEL_NAME, "temperature": 0, "response_format": {"type": "json_object"},
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
    usage = data["usage"]
    return {"text": data["choices"][0]["message"].get("content") or "",
            "tokens_in": usage["prompt_tokens"], "tokens_out": usage["completion_tokens"]}


def call_gemini(system, user):
    data = post_json(URL_GEMINI % MODEL_NAME, lambda key: {"x-goog-api-key": key},
                     {"systemInstruction": {"parts": [{"text": system}]},
                      "contents": [{"role": "user", "parts": [{"text": user}]}],
                      "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}})
    parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    usage = data["usageMetadata"]
    return {"text": text, "tokens_in": usage["promptTokenCount"],
            # token suy nghĩ tính tiền như token ra nên cộng vào
            "tokens_out": usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)}


PROVIDERS = {"groq": call_groq, "gemini": call_gemini}


@model_call
def call_model(system: str, user: str) -> dict:
    if MODEL_PROVIDER == "fake":
        # Chế độ giả KHÔNG đọc câu hỏi: luôn trả một kế hoạch cố định (hoặc không gán nhãn nào),
        # chỉ để luồng đi hết. agent.py gắn thẻ [GIẢ] vào câu trả lời khi model == "fake".
        text = "{}" if system.startswith("NHIỆM VỤ: GÁN NHÓM CHI") else FAKE_PLAN
        return {"text": text, "model": "fake", "tokens_in": 0, "tokens_out": 0}
    if MODEL_PROVIDER not in PROVIDERS:
        raise NotImplementedError("MODEL_PROVIDER=%s chưa được hỗ trợ trong codebase/ai.py (có: %s)"
                                  % (MODEL_PROVIDER, ", ".join(PROVIDERS)))
    r = PROVIDERS[MODEL_PROVIDER](system, user)
    return {"text": r["text"], "model": MODEL_NAME,
            "tokens_in": int(r["tokens_in"]), "tokens_out": int(r["tokens_out"])}
