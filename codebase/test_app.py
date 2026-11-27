"""Test phần hiển thị và bước xác nhận của app.py. Không gọi mạng.

    python -m unittest discover -s codebase -p "test_*.py"
"""
import contextlib
import io
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["MODEL_PROVIDER"] = "fake"

import agent  # noqa: E402
import app  # noqa: E402
import tools  # noqa: E402
from test_tools import ModelStub, spend_plan, TRUTH  # noqa: E402


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
        shown = app.render("  T0001 · 01/11/2026 · 5.000đ · «%s» · Không rõ" % ("x" * 100))
        self.assertIn("…", shown)
        self.assertTrue(all(len(line) < 100 for line in shown.split("\n")))


class TestConfirm(unittest.TestCase):
    def run_app(self, reply):
        tx_id = next(t["tx_id"] for t in TRUTH.values() if t["tag"] == "mo_ta_mo_ho")
        stub = ModelStub({"intent": "sua_nhom", "tx_id": tx_id, "new_category": "mua_sam"})
        feed = iter(["đổi nhóm", reply, "", ""])
        screen = io.StringIO()
        with mock.patch.object(agent, "call_model", stub), mock.patch("builtins.input", lambda *a: next(feed)), \
                mock.patch.object(tools, "apply_override") as write, mock.patch.object(tools, "USE_OVERRIDES", False), \
                contextlib.redirect_stdout(screen):
            self.assertEqual(app.main(), 0)
        return write, screen.getvalue()

    def test_writes_only_after_yes(self):
        write, screen = self.run_app("c")
        write.assert_called_once()
        self.assertIn("BẢN NHÁP", screen)

    def test_enter_writes_nothing(self):
        write, screen = self.run_app("")
        write.assert_not_called()
        self.assertIn("Không ghi gì", screen)


if __name__ == "__main__":
    unittest.main()
