"""Test phần hiển thị, vòng hỏi đáp, báo lỗi và bước xác nhận của app.py. Không gọi mạng.
File sửa nhóm luôn được trỏ vào thư mục tạm.

    python -m unittest discover -s codebase -p "test_*.py"
"""

import contextlib
import io
import json
import os
import runpy
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["MODEL_PROVIDER"] = "fake"

import agent  # noqa: E402  # import sau khi đặt sys.path và MODEL_PROVIDER=fake
import ai  # noqa: E402  # import sau khi đặt sys.path và MODEL_PROVIDER=fake
import app  # noqa: E402  # import sau khi đặt sys.path và MODEL_PROVIDER=fake
import tools  # noqa: E402  # import sau khi đặt sys.path và MODEL_PROVIDER=fake
import tracing  # noqa: E402  # import sau khi đặt sys.path và MODEL_PROVIDER=fake
from test_tools import TRUTH, ModelStub, spend_plan  # noqa: E402  # import sau khi đặt sys.path

MODEL_ERROR = "Mình chưa trả lời được vì lỗi gọi model."
LOCAL_ERROR = "Mình chưa trả lời được vì lỗi cục bộ (dữ liệu hoặc file sửa), không phải lỗi model."
SAVED = "Đã ghi vào data/overrides.json"
NOT_SAVED = "[lỗi] không ghi được thay đổi: "
VAGUE_TX = next(t["tx_id"] for t in TRUTH.values() if t["tag"] == "mo_ta_mo_ho")


def draft_plan():
    return {"intent": "sua_nhom", "tx_id": VAGUE_TX, "new_category": "mua_sam"}


class AppCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.path = os.path.join(self.dir, "overrides.json")
        for name, value in (("OVERRIDES_PATH", self.path), ("USE_OVERRIDES", False)):
            patcher = mock.patch.object(tools, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_main(self, inputs, stub=None):
        """Chạy app.main() thật. inputs: các lần gõ; phần tử là exception thì input() ném ra; hết danh sách → EOFError.
        stub: thay agent.call_model, bọc bằng tracing.model_call như call_model thật. None → giữ ai.call_model.
        → (mã thoát, màn hình, các lời nhắc của input)."""
        feed, prompts = iter(inputs), []

        def fake_input(prompt=""):
            prompts.append(prompt)
            value = next(feed, EOFError())
            if isinstance(value, BaseException):
                raise value
            return value

        model = agent.call_model if stub is None else tracing.model_call(stub.__call__)
        screen = io.StringIO()
        with (
            mock.patch("builtins.input", fake_input),
            mock.patch.object(agent, "call_model", model),
            contextlib.redirect_stdout(screen),
        ):
            code = app.main()
        return code, screen.getvalue(), prompts

    def stored(self):
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)


class TestRender(unittest.TestCase):
    def test_table_keeps_every_number_and_other_lines(self):
        stub = ModelStub(spend_plan())
        with mock.patch.object(agent, "call_model", stub):
            output = agent.answer("câu hỏi")["output"]
        shown = app.render(output)
        self.assertIn("Mã     Ngày", shown)
        self.assertNotIn(" · «", shown.split("Lưu ý:")[0])
        for line in output.split("\n"):
            match = app.ROW.match(line)
            if match:
                for part in match.groups()[:3]:
                    self.assertIn(part, shown)
            else:
                self.assertIn(line, shown)

    def test_long_description_is_clipped(self):
        shown = app.render(
            "  T0001 · 01/11/2026 · 5.000đ · «%s» · Không rõ" % ("x" * 100)
        )
        self.assertIn("…", shown)
        self.assertTrue(all(len(line) < 100 for line in shown.split("\n")))

    def test_footer_reports_the_measured_numbers(self):
        summary = {
            "models": ["m-a", "m-b"],
            "model_calls": 2,
            "tool_calls": 5,
            "tokens_in": 31,
            "tokens_out": 7,
        }
        self.assertEqual(
            app.footer(summary, 1.25),
            "model m-a, m-b · gọi model 2 lần · công cụ 5 lần · token vào 31 / ra 7 · 1.2 giây",
        )
        self.assertTrue(
            app.footer(dict(summary, models=[]), 0).startswith("model — · ")
        )


class TestConfirm(AppCase):
    def run_confirm(self, reply):
        with mock.patch.object(tools, "apply_override") as write:
            code, screen, prompts = self.run_main(
                ["đổi nhóm", reply, "", ""], ModelStub(draft_plan())
            )
        self.assertEqual(code, 0)
        self.assertIn("Ghi thay đổi này?", prompts[1])
        return write, screen

    def test_writes_only_after_yes(self):
        for reply in ("c", " C "):
            with self.subTest(reply=reply):
                write, screen = self.run_confirm(reply)
                write.assert_called_once_with(VAGUE_TX, "mua_sam")
                self.assertIn("BẢN NHÁP", screen)
                self.assertIn(SAVED, screen)

    def test_enter_writes_nothing(self):
        for reply in ("", "k", "co"):
            with self.subTest(reply=reply):
                write, screen = self.run_confirm(reply)
                write.assert_not_called()
                self.assertIn("Không ghi gì", screen)

    def test_end_of_input_or_ctrl_c_at_confirm_writes_nothing(self):
        for stop in (EOFError(), KeyboardInterrupt()):
            with self.subTest(stop=type(stop).__name__):
                write, screen = self.run_confirm(stop)
                write.assert_not_called()
                self.assertIn("Không ghi gì", screen)
                self.assertNotIn(SAVED, screen)

    def test_yes_writes_the_file(self):
        code, screen, _ = self.run_main(["đổi nhóm", "c"], ModelStub(draft_plan()))
        self.assertEqual(code, 0)
        self.assertIn(SAVED, screen)
        self.assertEqual(self.stored(), {VAGUE_TX: "mua_sam"})

    def test_failed_write_is_reported_and_the_loop_continues(self):
        stub = ModelStub(draft_plan())
        with mock.patch.object(
            tools.os, "replace", side_effect=PermissionError("khoa file")
        ):
            code, screen, prompts = self.run_main(
                ["đổi nhóm", "c", "đổi nhóm lần hai", "", "", ""], stub
            )
        self.assertEqual(code, 0)
        self.assertIn(NOT_SAVED + "PermissionError: khoa file", screen)
        self.assertNotIn(SAVED, screen)
        self.assertEqual(len(stub.calls), 2)  # câu thứ hai vẫn được hỏi
        self.assertEqual(os.listdir(self.dir), [])

    def test_bad_existing_file_at_write_time_is_reported(self):
        real = agent.answer

        def answer_then_corrupt(text):
            result = real(text)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"T9999": "vang"}, f)
            return result

        with mock.patch.object(agent, "answer", answer_then_corrupt):
            code, screen, _ = self.run_main(["đổi nhóm", "c"], ModelStub(draft_plan()))
        self.assertEqual(code, 0)
        self.assertIn(NOT_SAVED + "ValueError: " + self.path, screen)
        self.assertNotIn(SAVED, screen)
        self.assertEqual(self.stored(), {"T9999": "vang"})


class TestErrors(AppCase):
    def assert_local(self, screen, kind):
        self.assertIn(LOCAL_ERROR, screen)
        self.assertIn("[lỗi] cục bộ: %s: " % kind, screen)
        self.assertNotIn(MODEL_ERROR, screen)
        self.assertNotIn("[lỗi] model:", screen)

    def test_model_failure_through_real_call_model(self):
        calls = []

        def no_candidates(request, timeout=None):
            calls.append(request)
            return io.BytesIO(b'{"candidates": []}')

        with (
            mock.patch.multiple(
                ai,
                MODEL_PROVIDER="gemini",
                MODEL_NAME="model-x",
                API_KEYS=["khoa-gia-app-0000"],
                _key_index=0,
            ),
            mock.patch.object(ai.urllib.request, "urlopen", no_candidates),
        ):
            code, screen, _ = self.run_main(["câu một", "câu hai"])
        self.assertEqual((code, len(calls)), (0, 2))  # báo lỗi rồi hỏi tiếp
        self.assertEqual(screen.count(MODEL_ERROR), 2)
        self.assertIn("[lỗi] model: ModelError: Gemini không trả chữ", screen)
        self.assertNotIn("cục bộ", screen)
        self.assertNotIn("khoa-gia", screen)
        self.assertNotIn("token vào", screen)  # không in câu trả lời hay chân trang

    def test_any_error_escaping_call_model_counts_as_model_error(self):
        class Broken(ModelStub):
            def __call__(self, system, user):
                raise ConnectionError("mat mang")

        code, screen, _ = self.run_main(["câu"], Broken({}))
        self.assertEqual(code, 0)
        self.assertIn("[lỗi] model: ConnectionError: mat mang", screen)
        self.assertNotIn("cục bộ", screen)

    def test_missing_statement_file_is_a_local_error(self):
        with mock.patch.object(
            tools, "TX_PATH", os.path.join(self.dir, "khong-co.csv")
        ):
            code, screen, prompts = self.run_main(["tổng chi"], ModelStub(spend_plan()))
        self.assertEqual(code, 0)
        self.assert_local(screen, "FileNotFoundError")
        self.assertEqual(len(prompts), 2)

    def test_bad_overrides_file_is_a_local_error_even_after_a_good_model_call(self):
        for content, kind in (
            ("{khong json", "JSONDecodeError"),
            (json.dumps({VAGUE_TX: "vang"}), "ValueError"),
            ("[]", "ValueError"),
        ):
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(content)
            with self.subTest(content=content):
                code, screen, _ = self.run_main(["tổng chi"], ModelStub(spend_plan()))
                self.assertEqual(code, 0)
                self.assert_local(screen, kind)

    def test_provider_not_connected_returns_1(self):
        with mock.patch.object(ai, "MODEL_PROVIDER", "khac"):
            code, screen, prompts = self.run_main(["câu hỏi", "câu nữa"])
        self.assertEqual((code, len(prompts)), (1, 1))
        self.assertIn("Chưa nối model: MODEL_PROVIDER=khac", screen)
        self.assertIsNone(tracing._case["events"])  # phiên trace đã đóng

    def test_load_failure_returns_1_and_asks_nothing(self):
        with mock.patch.dict(sys.modules, {"agent": None}):
            code, screen, prompts = self.run_main(["câu hỏi"])
        self.assertEqual((code, prompts), (1, []))
        self.assertIn(
            "Không nạp được codebase/ — lỗi ở codebase/app.py: ModuleNotFoundError",
            screen,
        )
        self.assertIn("docs/connect-model.md", screen)

    def test_where_names_the_broken_file(self):
        broken = SyntaxError("hong")
        broken.filename = os.path.join(HERE, "agent.py")
        self.assertEqual(app._where(broken), "codebase/agent.py")
        self.assertEqual(app._where(ValueError("không có traceback")), "codebase/")
        outside = SyntaxError("hong")
        outside.filename = os.path.join(self.dir, "x.py")
        self.assertEqual(app._where(outside), outside.filename)


class TestSession(AppCase):
    def test_fake_mode_banner_answer_and_footer(self):
        with mock.patch.object(ai, "MODEL_PROVIDER", "fake"):
            code, screen, _ = self.run_main(["Tiền ăn tháng này?"])
        self.assertEqual(code, 0)
        self.assertIn("dữ liệu GIẢ LẬP · CHẾ ĐỘ GIẢ (chưa nối model)", screen)
        self.assertIn(agent.FAKE_TAG, screen)
        self.assertRegex(
            screen,
            r"model fake · gọi model 2 lần · công cụ [1-9]\d* lần · token vào 0 / ra 0 · "
            r"\d+\.\d giây",
        )

    def test_real_provider_banner_names_the_model(self):
        with mock.patch.multiple(ai, MODEL_PROVIDER="gemini", MODEL_NAME="model-x"):
            code, screen, _ = self.run_main([])
        self.assertEqual(code, 0)
        self.assertIn("dữ liệu GIẢ LẬP · model model-x", screen)
        self.assertNotIn("CHẾ ĐỘ GIẢ", screen)

    def test_two_blank_lines_exit_and_a_question_resets_the_count(self):
        stub = ModelStub(spend_plan())
        code, _, prompts = self.run_main(
            ["", "câu", "  ", "câu", "", "", "không được đọc"], stub
        )
        self.assertEqual((code, len(prompts)), (0, 6))
        asked = [
            user
            for system, user in stub.calls
            if not system.startswith(agent.LABEL_TASK)
        ]
        self.assertEqual(asked, ["câu", "câu"])

    def test_ctrl_c_at_question_exits_cleanly(self):
        code, _, prompts = self.run_main([KeyboardInterrupt()])
        self.assertEqual((code, len(prompts)), (0, 1))

    def test_piped_question_is_echoed(self):
        with mock.patch.object(sys, "stdin", io.StringIO()):
            _, screen, _ = self.run_main(["câu hỏi qua ống"], ModelStub(spend_plan()))
        self.assertIn("câu hỏi qua ống\n", screen)

    def test_app_reads_confirmed_overrides(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({VAGUE_TX: "giao_duc"}, f)
        rows = tools.get_transactions("2026-09-01", "2026-11-27")["transactions"]
        date = next(t["date"] for t in rows if t["tx_id"] == VAGUE_TX)
        plan = spend_plan("theo_nhom", date, date, category="giao_duc")
        self.assertFalse(tools.USE_OVERRIDES)
        _, screen, _ = self.run_main(["tiền học"], ModelStub(plan, label_reply="{}"))
        self.assertTrue(tools.USE_OVERRIDES)
        self.assertRegex(screen, r"(?m)^  %s " % VAGUE_TX)


class TestStreams(unittest.TestCase):
    def load_with(self, **streams):
        with (
            mock.patch.multiple(sys, **streams),
            mock.patch.object(sys, "path", list(sys.path)),
        ):
            runpy.run_path(os.path.join(HERE, "app.py"), run_name="khong_chay_main")

    def test_text_streams_are_switched_to_utf8(self):
        streams = {
            name: io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
            for name in ("stdout", "stderr", "stdin")
        }
        self.load_with(**streams)
        self.assertEqual(
            {(s.encoding, s.errors) for s in streams.values()}, {("utf-8", "replace")}
        )

    def test_other_streams_are_left_alone(self):
        class NoReconfigure(io.StringIO):
            def reconfigure(self, **kwargs):
                raise AssertionError("không được gọi")

        self.load_with(
            stdout=NoReconfigure(), stderr=NoReconfigure(), stdin=NoReconfigure()
        )


if __name__ == "__main__":
    unittest.main()
