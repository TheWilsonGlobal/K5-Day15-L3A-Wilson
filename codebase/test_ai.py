"""Test phần nối model mà không gọi mạng: urlopen được thay bằng phản hồi dựng sẵn, khoá là chuỗi giả.

python -m unittest discover -s codebase -p "test_*.py"
"""

import contextlib
import http.client
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["MODEL_PROVIDER"] = "fake"

import ai  # noqa: E402  # import sau khi đặt sys.path và MODEL_PROVIDER=fake
import tracing  # noqa: E402  # import sau khi đặt sys.path và MODEL_PROVIDER=fake

KEYS = ["khoa-gia-mot-0000", "khoa-gia-hai-0000"]
GROQ = {
    "choices": [{"message": {"content": '{"a":1}'}}],
    "usage": {"prompt_tokens": 11, "completion_tokens": 7},
}
GEMINI = {
    "candidates": [
        {"content": {"parts": [{"text": "nghĩ", "thought": True}, {"text": '{"a":1}'}]}}
    ],
    "usageMetadata": {
        "promptTokenCount": 13,
        "candidatesTokenCount": 5,
        "thoughtsTokenCount": 3,
    },
}


class FakeNet:
    """Trả lần lượt: số nguyên → lỗi HTTP mã đó (thân lỗi có chứa khoá); exception → ném ra;
    bytes → thân phản hồi nguyên văn; giá trị khác → phản hồi JSON."""

    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, int):
            body = io.BytesIO(
                ("loi voi khoa %s va gsk_abcdef123456" % KEYS[0]).encode("utf-8")
            )
            raise urllib.error.HTTPError(request.full_url, reply, "x", {}, body)
        if isinstance(reply, BaseException):
            raise reply
        if isinstance(reply, bytes):
            return io.BytesIO(reply)
        return io.BytesIO(json.dumps(reply).encode("utf-8"))


def groq(content="{}", usage=None, **choice):
    return {
        "choices": [dict({"message": {"content": content}}, **choice)],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2}
        if usage is None
        else usage,
    }


def gemini(parts=({"text": "{}"},), usage=None):
    return {
        "candidates": [{"content": {"parts": list(parts)}}],
        "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 2}
        if usage is None
        else usage,
    }


def newline_header(request, timeout=None):
    """Đường lỗi thật của http.client: header có ký tự xuống dòng bị từ chối bằng ValueError, trước khi mở kết nối."""
    connection = http.client.HTTPConnection("khong-ket-noi.invalid")
    connection.putrequest("POST", "/")
    for name, value in request.header_items():
        connection.putheader(name, value)
    raise AssertionError("http.client đã nhận header có xuống dòng")


class TestProviders(unittest.TestCase):
    def call(self, provider, *replies):
        net = FakeNet(*replies)
        with (
            mock.patch.multiple(
                ai,
                MODEL_PROVIDER=provider,
                MODEL_NAME="model-x",
                API_KEYS=list(KEYS),
                _key_index=0,
            ),
            mock.patch.object(ai.urllib.request, "urlopen", net),
        ):
            return ai.call_model("hệ thống", "câu hỏi"), net

    def test_groq_reads_text_and_usage(self):
        result, net = self.call("groq", GROQ)
        self.assertEqual(
            result,
            {"text": '{"a":1}', "model": "model-x", "tokens_in": 11, "tokens_out": 7},
        )
        self.assertEqual(
            net.requests[0].get_header("Authorization"), "Bearer " + KEYS[0]
        )

    def test_gemini_counts_thinking_tokens_and_keeps_key_out_of_url(self):
        result, net = self.call("gemini", GEMINI)
        self.assertEqual(
            result,
            {"text": '{"a":1}', "model": "model-x", "tokens_in": 13, "tokens_out": 8},
        )
        self.assertNotIn(KEYS[0], net.requests[0].full_url)
        self.assertEqual(net.requests[0].get_header("X-goog-api-key"), KEYS[0])

    def test_429_rotates_to_next_key(self):
        result, net = self.call("groq", 429, GROQ)
        self.assertEqual(result["tokens_in"], 11)
        self.assertEqual(
            [r.get_header("Authorization") for r in net.requests],
            ["Bearer " + k for k in KEYS],
        )

    def test_all_keys_limited_raises_without_leaking_keys(self):
        with self.assertRaises(ai.ModelError) as caught:
            self.call("groq", 429, 429)
        message = str(caught.exception)
        self.assertIn("HTTP 429 (đã thử 2 khoá)", message)
        self.assertNotIn(KEYS[0], message)
        self.assertNotIn("gsk_abcdef", message)

    def test_other_errors_do_not_rotate(self):
        net = FakeNet(401, GROQ)
        with (
            mock.patch.multiple(
                ai, MODEL_PROVIDER="groq", API_KEYS=list(KEYS), _key_index=0
            ),
            mock.patch.object(ai.urllib.request, "urlopen", net),
            self.assertRaises(ai.ModelError),
        ):
            ai.call_model("a", "b")
        self.assertEqual(len(net.requests), 1)

    def test_unknown_provider(self):
        with (
            mock.patch.object(ai, "MODEL_PROVIDER", "khac"),
            self.assertRaises(NotImplementedError),
        ):
            ai.call_model("a", "b")

    def test_env_example_has_no_values(self):
        with open(os.path.join(ai.ROOT, ".env.example"), encoding="utf-8-sig") as f:
            lines = [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]
        self.assertEqual(
            lines, ["MODEL_PROVIDER=", "MODEL_NAME=", "API_KEY=", "API_KEYS="]
        )


class ModelCase(unittest.TestCase):
    def call(self, provider, *replies, keys=KEYS, urlopen=None):
        """Gọi ai.call_model thật, chỉ thay urlopen. → (kết quả, lỗi, sự kiện trace)."""
        net = urlopen or FakeNet(*replies)
        result = error = None
        with (
            mock.patch.multiple(
                ai,
                MODEL_PROVIDER=provider,
                MODEL_NAME="model-x",
                API_KEYS=list(keys),
                _key_index=0,
            ),
            mock.patch.object(ai.urllib.request, "urlopen", net),
        ):
            tracing.begin("test")
            try:
                result = ai.call_model("hệ thống", "câu hỏi")
            except Exception as e:  # kiểu lỗi được kiểm ở assert_model_error
                error = e
            finally:
                _, events = tracing.end()
        return result, error, events

    def assert_model_error(self, outcome, *words):
        result, error, events = outcome
        self.assertIsNone(result)
        self.assertIsInstance(error, ai.ModelError, repr(error))
        for word in words:
            self.assertIn(word, str(error))
        # lỗi được ghi vào trace dạng lỗi của model (app.py dựa vào đây để phân loại)
        self.assertEqual([e["kind"] for e in events if e.get("error")], ["model"])
        return str(error)


class TestModelErrors(ModelCase):
    def test_model_error_is_a_runtime_error(self):
        self.assertTrue(issubclass(ai.ModelError, RuntimeError))

    def test_gemini_without_text_names_the_reason(self):
        usage = {"promptTokenCount": 9, "candidatesTokenCount": 0}
        cases = {
            "no candidates": (
                {"promptFeedback": {"blockReason": "SAFETY"}, "usageMetadata": usage},
                "blockReason=SAFETY",
            ),
            "candidates []": (
                {"candidates": [], "usageMetadata": usage},
                "blockReason=không có",
            ),
            "candidate not object": (
                {"candidates": ["x"], "usageMetadata": usage},
                "finishReason=không có",
            ),
            "no content": (
                {
                    "candidates": [{"finishReason": "MAX_TOKENS"}],
                    "usageMetadata": usage,
                },
                "finishReason=MAX_TOKENS",
            ),
            "no parts": (gemini(parts=()), "blockReason="),
            "empty text": (gemini(parts=[{"text": ""}]), "blockReason="),
            "blank text": (gemini(parts=[{"text": " \n "}]), "blockReason="),
            "part without text": (
                gemini(parts=[{"inlineData": {}}, "x"]),
                "blockReason=",
            ),
            "thought only": (
                gemini(parts=[{"text": "nghĩ", "thought": True}]),
                "blockReason=",
            ),
        }
        for name, (body, word) in cases.items():
            with self.subTest(name):
                self.assert_model_error(
                    self.call("gemini", body), "Gemini không trả chữ", word
                )

    def test_groq_without_text_raises(self):
        usage = {"prompt_tokens": 9, "completion_tokens": 0}
        for content in ("", "  ", None, ["a"]):
            with self.subTest(content=content):
                self.assert_model_error(
                    self.call("groq", groq(content, usage, finish_reason="length")),
                    "Groq không trả chữ",
                    "finish_reason=length",
                )
        for body in (
            {"choices": [{}], "usage": usage},
            {"choices": [{"message": None}], "usage": usage},
        ):
            with self.subTest(body=body):
                self.assert_model_error(self.call("groq", body), "Groq không trả chữ")
        for body in (
            {"choices": [], "usage": usage},
            {"usage": usage},
            {"choices": None},
            {"choices": ["x"]},
            {"choices": {"a": 1}},
        ):
            with self.subTest(body=body):
                self.assert_model_error(self.call("groq", body), "choices")

    def test_missing_or_non_integer_token_count_raises(self):
        providers = {
            "groq": (
                ("prompt_tokens", "completion_tokens"),
                lambda usage: groq(usage=usage),
            ),
            "gemini": (
                ("promptTokenCount", "candidatesTokenCount"),
                lambda usage: gemini(usage=usage),
            ),
        }
        missing = object()
        for provider, (names, build) in providers.items():
            for name in names:
                for bad in (missing, None, 3.0, 2.5, "7", True, [1]):
                    usage = dict.fromkeys(names, 4)
                    if bad is missing:
                        del usage[name]
                    else:
                        usage[name] = bad
                    with self.subTest(
                        provider=provider,
                        key=name,
                        value="thiếu" if bad is missing else bad,
                    ):
                        self.assert_model_error(
                            self.call(provider, build(usage)),
                            name,
                            "không ước lượng token",
                        )

    def test_gemini_thought_count_must_be_a_non_negative_int(self):
        for bad in (2.5, True, False, "3", None, -1):
            with self.subTest(value=bad):
                usage = {
                    "promptTokenCount": 4,
                    "candidatesTokenCount": 4,
                    "thoughtsTokenCount": bad,
                }
                self.assert_model_error(
                    self.call("gemini", gemini(usage=usage)), "thoughtsTokenCount"
                )

    def test_gemini_thought_count_zero_is_counted_and_absent_is_zero(self):
        usage = {
            "promptTokenCount": 4,
            "candidatesTokenCount": 4,
            "thoughtsTokenCount": 0,
        }
        result, error, _ = self.call("gemini", gemini(usage=usage))
        self.assertIsNone(error)
        self.assertEqual(result["tokens_out"], 4)
        usage = {"promptTokenCount": 4, "candidatesTokenCount": 4}
        result, error, _ = self.call("gemini", gemini(usage=usage))
        self.assertIsNone(error)
        self.assertEqual(result["tokens_out"], 4)

    def test_missing_usage_object_raises(self):
        bodies = {
            "groq": [{"choices": groq()["choices"]}, groq(usage=[]), groq(usage="x")],
            "gemini": [
                {"candidates": gemini()["candidates"]},
                gemini(usage=[]),
                gemini(usage="x"),
            ],
        }
        for provider, cases in bodies.items():
            for body in cases:
                with self.subTest(provider=provider, body=body):
                    self.assert_model_error(
                        self.call(provider, body), "không ước lượng token"
                    )

    def test_zero_tokens_and_absent_thought_count_are_valid(self):
        result, error, _ = self.call(
            "gemini", gemini(usage={"promptTokenCount": 0, "candidatesTokenCount": 0})
        )
        self.assertIsNone(error)
        self.assertEqual((result["tokens_in"], result["tokens_out"]), (0, 0))
        result, error, _ = self.call("gemini", gemini())
        self.assertIsNone(error)
        self.assertEqual((result["text"], result["tokens_out"]), ("{}", 2))

    def test_response_that_is_not_an_object_raises(self):
        for body in ([], [1], "x", 5, None):
            for provider in ("groq", "gemini"):
                with self.subTest(provider=provider, body=body):
                    reply = json.dumps(body).encode("utf-8")
                    self.assert_model_error(
                        self.call(provider, reply), "không phải JSON object"
                    )

    def test_unreadable_response_raises(self):
        for body, kind in (
            (b"<html>", "JSONDecodeError"),
            (b"\xff\xfe\x00", "UnicodeDecodeError"),
        ):
            with self.subTest(kind):
                self.assert_model_error(self.call("groq", body), kind)

    def test_no_key_raises_before_any_request(self):
        net = FakeNet()
        self.assert_model_error(
            self.call("groq", keys=[], urlopen=net), "chưa có API_KEY"
        )
        self.assertEqual(net.requests, [])


class TestRedaction(ModelCase):
    def assert_redacted(self, outcome, kind):
        message = self.assert_model_error(outcome, kind, "[khoá]")
        self.assertNotIn("khoa-gia", message)
        error = outcome[1]
        self.assertIsNone(error.__cause__)
        self.assertTrue(
            error.__suppress_context__
        )  # traceback không in lại lỗi gốc còn chứa khoá
        self.assertNotIn("khoa-gia", str(outcome[2]))

    def test_every_transport_exception_is_redacted(self):
        text = "hỏng với " + KEYS[0]
        errors = (
            urllib.error.URLError(text),
            TimeoutError(text),
            ConnectionResetError(text),
            OSError(text),
            ValueError(text),
            RuntimeError(text),
            http.client.RemoteDisconnected(text),
        )
        for exc in errors:
            for provider in ("groq", "gemini"):
                with self.subTest(provider=provider, kind=type(exc).__name__):
                    self.assert_redacted(self.call(provider, exc), type(exc).__name__)

    def test_key_with_newline_in_header_value_error_is_redacted(self):
        for provider in ("groq", "gemini"):
            with self.subTest(provider):
                outcome = self.call(
                    provider, keys=["khoa-gia\nxuong-dong-0000"], urlopen=newline_header
                )
                self.assert_redacted(outcome, "ValueError")
                self.assertNotIn("xuong-dong", str(outcome[1]))

    def test_error_from_building_the_header_is_redacted(self):
        def auth(key):
            raise KeyError(key)

        with (
            mock.patch.object(ai, "API_KEYS", list(KEYS)),
            mock.patch.object(ai, "_key_index", 0),
            self.assertRaises(ai.ModelError) as caught,
        ):
            ai.post_json("https://khong-ket-noi.invalid", auth, {})
        self.assertIn("KeyError", str(caught.exception))
        self.assertNotIn(KEYS[0], str(caught.exception))

    def test_longer_key_containing_a_shorter_one_leaves_no_tail(self):
        with mock.patch.object(
            ai, "API_KEYS", ["khoa-gia-ngan", "khoa-gia-ngan-phan-duoi"]
        ):
            self.assertEqual(
                ai.redact("a khoa-gia-ngan-phan-duoi b khoa-gia-ngan"),
                "a [khoá] b [khoá]",
            )

    def test_key_in_latin1_bytes_repr_is_redacted(self):
        key = "khoa-é-gia\nxuong"
        bytes_form = repr(key.encode("latin-1", "replace"))[
            2:-1
        ]  # b'...' bỏ tiền tố: «\xe9», «\n» thành chữ
        with mock.patch.object(ai, "API_KEYS", [key]):
            self.assertEqual(
                ai.redact("lỗi " + bytes_form + " và " + repr(key)[1:-1]),
                "lỗi [khoá] và [khoá]",
            )
            self.assertEqual(ai.redact("lỗi " + key), "lỗi [khoá]")

    def test_key_shaped_strings_are_redacted_even_when_not_configured(self):
        with mock.patch.object(ai, "API_KEYS", []):
            for fake in (
                "gsk_abcdef123456",
                "sk-abcdef123456",
                "AIzaabcdef123456",
                "AQ.abcdef123456",
            ):
                self.assertEqual(ai.redact("x %s y" % fake), "x [khoá] y", fake)

    def test_raw_response_print_is_redacted(self):
        screen = io.StringIO()
        with (
            mock.patch.object(ai, "SHOW_RAW", True),
            contextlib.redirect_stdout(screen),
        ):
            result, error, _ = self.call("groq", dict(groq(), echo=KEYS[0]))
        self.assertIsNone(error)
        self.assertEqual(result["tokens_in"], 3)
        self.assertIn('"echo": "[khoá]"', screen.getvalue())
        self.assertNotIn(KEYS[0], screen.getvalue())


class TestLoadEnv(unittest.TestCase):
    def load(self, text, before):
        """Đọc một file env dựng riêng trong thư mục tạm (không phải .env của repo) trên môi trường sạch."""
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(os.environ, before, clear=True),
        ):
            path = os.path.join(tmp, "env-gia")
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write(text)
            ai.load_env(path)
            return dict(os.environ)

    def test_existing_variables_are_not_overridden(self):
        got = self.load(
            "AA=tu-file\nBB=tu-file\nCC=tu-file\n", {"AA": "co-san", "CC": ""}
        )
        self.assertEqual(got, {"AA": "co-san", "BB": "tu-file", "CC": ""})

    def test_parsing_skips_comments_and_strips_quotes(self):
        got = self.load(
            "# XX=1\n\nkhong co dau bang\n DD = \"nhay kep\" \nEE='nhay don'\nFF=a=b\n",
            {},
        )
        self.assertEqual(got, {"DD": "nhay kep", "EE": "nhay don", "FF": "a=b"})

    def test_missing_file_changes_nothing(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(os.environ, {"AA": "1"}, clear=True),
        ):
            ai.load_env(os.path.join(tmp, "khong-co"))
            self.assertEqual(dict(os.environ), {"AA": "1"})


if __name__ == "__main__":
    unittest.main()
