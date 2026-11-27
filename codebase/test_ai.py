"""Test phần nối model mà không gọi mạng: urlopen được thay bằng phản hồi dựng sẵn, khoá là chuỗi giả.

    python -m unittest discover -s codebase -p "test_*.py"
"""
import io
import json
import os
import sys
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["MODEL_PROVIDER"] = "fake"

import ai  # noqa: E402

KEYS = ["khoa-gia-mot-0000", "khoa-gia-hai-0000"]
GROQ = {"choices": [{"message": {"content": "{\"a\":1}"}}], "usage": {"prompt_tokens": 11, "completion_tokens": 7}}
GEMINI = {"candidates": [{"content": {"parts": [{"text": "nghĩ", "thought": True}, {"text": "{\"a\":1}"}]}}],
          "usageMetadata": {"promptTokenCount": 13, "candidatesTokenCount": 5, "thoughtsTokenCount": 3}}


class FakeNet:
    """Trả lần lượt: số nguyên → lỗi HTTP mã đó (thân lỗi có chứa khoá); dict → phản hồi thành công."""

    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, int):
            body = io.BytesIO(("loi voi khoa %s va gsk_abcdef123456" % KEYS[0]).encode("utf-8"))
            raise urllib.error.HTTPError(request.full_url, reply, "x", {}, body)
        return io.BytesIO(json.dumps(reply).encode("utf-8"))


class TestProviders(unittest.TestCase):
    def call(self, provider, *replies):
        net = FakeNet(*replies)
        with mock.patch.multiple(ai, MODEL_PROVIDER=provider, MODEL_NAME="model-x", API_KEYS=list(KEYS),
                                 _key_index=0), mock.patch.object(ai.urllib.request, "urlopen", net):
            return ai.call_model("hệ thống", "câu hỏi"), net

    def test_groq_reads_text_and_usage(self):
        result, net = self.call("groq", GROQ)
        self.assertEqual(result, {"text": "{\"a\":1}", "model": "model-x", "tokens_in": 11, "tokens_out": 7})
        self.assertEqual(net.requests[0].get_header("Authorization"), "Bearer " + KEYS[0])

    def test_gemini_counts_thinking_tokens_and_keeps_key_out_of_url(self):
        result, net = self.call("gemini", GEMINI)
        self.assertEqual(result, {"text": "{\"a\":1}", "model": "model-x", "tokens_in": 13, "tokens_out": 8})
        self.assertNotIn(KEYS[0], net.requests[0].full_url)
        self.assertEqual(net.requests[0].get_header("X-goog-api-key"), KEYS[0])

    def test_429_rotates_to_next_key(self):
        result, net = self.call("groq", 429, GROQ)
        self.assertEqual(result["tokens_in"], 11)
        self.assertEqual([r.get_header("Authorization") for r in net.requests], ["Bearer " + k for k in KEYS])

    def test_all_keys_limited_raises_without_leaking_keys(self):
        with self.assertRaises(RuntimeError) as caught:
            self.call("groq", 429, 429)
        message = str(caught.exception)
        self.assertIn("HTTP 429 (đã thử 2 khoá)", message)
        self.assertNotIn(KEYS[0], message)
        self.assertNotIn("gsk_abcdef", message)

    def test_other_errors_do_not_rotate(self):
        net = FakeNet(401, GROQ)
        with mock.patch.multiple(ai, MODEL_PROVIDER="groq", API_KEYS=list(KEYS), _key_index=0), \
                mock.patch.object(ai.urllib.request, "urlopen", net), self.assertRaises(RuntimeError):
            ai.call_model("a", "b")
        self.assertEqual(len(net.requests), 1)

    def test_unknown_provider(self):
        with mock.patch.object(ai, "MODEL_PROVIDER", "khac"), self.assertRaises(NotImplementedError):
            ai.call_model("a", "b")

    def test_env_example_has_no_values(self):
        with open(os.path.join(ai.ROOT, ".env.example"), encoding="utf-8-sig") as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        self.assertEqual(lines, ["MODEL_PROVIDER=", "MODEL_NAME=", "API_KEY=", "API_KEYS="])


if __name__ == "__main__":
    unittest.main()
