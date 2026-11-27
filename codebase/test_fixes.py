"""Test cho các sửa đổi giữa lượt 1 và lượt 2: mô tả chỉ có mã hoá đơn, câu hỏi bị hiểu sai ở prompt kế hoạch,
tên nơi bán có từ chỉ loại hình, và lời gọi gán nhóm bị lỗi (RV-01). Không gọi model thật.

    python -m unittest discover -s codebase -p "test_*.py"
"""

import json
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "eval"))
os.environ["MODEL_PROVIDER"] = "fake"

import agent  # noqa: E402  # import sau khi đặt sys.path và MODEL_PROVIDER=fake
import ai  # noqa: E402  # như trên
import grade  # noqa: E402  # như trên
import tools  # noqa: E402  # như trên
import tracing  # noqa: E402  # như trên
from test_agent import LABEL_FAILED, NOVEMBER, row, statement, warnings  # noqa: E402
from test_tools import ModelStub, ask, spend_plan  # noqa: E402

BARE = (
    "THANH TOAN HD 778120",
    "TT HD 5521",
    "Thanh toán hoá đơn số 0091",
    "THANHTOAN HD123456",
    "TT HOA DON MA 77",
)
NAMED = (
    "THANH TOAN HD DIEN 778120",
    "THANH TOAN HD INTERNET 12",
    "TT DON SHOPVUI 55210",
    "TIEN DIEN T10 PE0421",
    "QR 99812 TT",
    "THANH TOAN 5512",
    "NHA THUOC BINH MINH",
)


class TestBareBillCode(unittest.TestCase):
    def test_bare_bill_code_is_recognised(self):
        for text in BARE:
            with self.subTest(text):
                self.assertTrue(tools.is_bare_bill_code(text))

    def test_description_naming_a_service_or_merchant_is_left_alone(self):
        for text in NAMED:
            with self.subTest(text):
                self.assertFalse(tools.is_bare_bill_code(text))

    def test_model_label_cannot_override_the_rule(self):
        text = BARE[0]
        labels = {tools.description_key(text): "hoa_don"}
        (tx,) = tools.categorize([row("T0001", 160000, text)], labels)
        self.assertEqual((tx["category"], tx["basis"]), ("khong_ro", "thieu_noi_dung"))

    def test_bare_code_is_not_sent_to_the_labelling_call(self):
        with statement(
            row("T0001", 160000, BARE[0]), row("T0002", 50000, "LAU NUONG 99")
        ):
            out, stub = ask(spend_plan(**NOVEMBER), label_reply='{"1": "an_uong"}')
        sent = [json.loads(u) for s, u in stub.calls if s == agent.SYSTEM_LABEL]
        self.assertEqual(
            [[i["mo_ta"] for i in items] for items in sent], [["LAU NUONG 99"]]
        )
        self.assertIn("Chưa rõ nhóm: 160.000đ (1 giao dịch)", out["output"])

    def test_confirmed_user_override_still_wins(self):
        tx = row("T0001", 160000, BARE[0])
        _, category, basis = tools._classify(tx, None, {"T0001": "hoa_don"})
        self.assertEqual((category, basis), ("hoa_don", "nguoi_dung"))


class TestPlanPrompt(unittest.TestCase):
    """Hành vi của model đo bằng lượt eval; ở đây chỉ giữ cho các quy tắc không bị xoá nhầm."""

    def test_refund_question_is_a_spending_question(self):
        self.assertIn("tiền đã được hoàn", agent.SYSTEM_PLAN)
        self.assertIn("là hỏi chi tiêu: tong_chi", agent.SYSTEM_PLAN)
        self.assertIn("THỰC HIỆN chuyển, trả, huỷ, hoàn tiền", agent.SYSTEM_PLAN)

    def test_grouping_a_period_is_not_a_recategorize_request(self):
        self.assertIn("NHIỀU khoản chi trong một khoảng thời gian", agent.SYSTEM_PLAN)
        self.assertIn("sua_nhom chỉ khi", agent.SYSTEM_PLAN)

    def test_prompt_still_formats(self):
        out, stub = ask(spend_plan(**NOVEMBER), label_reply="{}")
        self.assertNotIn("%(", stub.calls[0][0])
        self.assertIn("chưa trừ vào tổng chi", out["output"])


class TestMerchantPrefix(unittest.TestCase):
    ROWS = (
        row("T0001", 50000, "COM CO BA"),
        row("T0002", 40000, "comcoba qr"),
        row("T0003", 30000, "SHOPVUI*ORDER"),
        row("T0004", 20000, "THOI TRANG LINEN HOUSE"),
        row("T0005", 10000, "PHONG KHAM RANG NU CUOI"),
    )

    def found(self, keyword):
        categorized = tools.categorize(list(self.ROWS))
        return [
            t["tx_id"]
            for t in tools.find_merchant(categorized, keyword)["transactions"]
        ]

    def test_venue_words_are_ignored(self):
        for keyword in (
            "Quán Cơm Cô Ba",
            "quan com co ba",
            "Tiệm cơm cô Ba",
            "Nhà hàng Cơm Cô Ba",
            "cửa hàng Cơm Cô Ba",
            "Quán cửa hàng Cơm Cô Ba",
        ):
            with self.subTest(keyword):
                self.assertEqual(self.found(keyword), ["T0001", "T0002"])

    def test_name_that_contains_the_venue_word_still_matches(self):
        self.assertEqual(self.found("ShopVui"), ["T0003"])
        self.assertEqual(self.found("shop vui"), ["T0003"])

    def test_short_remainder_does_not_widen_the_search(self):
        self.assertEqual(self.found("Quán Nu"), [])
        self.assertEqual(self.found("quán"), [])

    def test_word_with_other_diacritics_is_not_a_venue_word(self):
        self.assertEqual(self.found("quần house"), [])


class TestLabelCallFailure(unittest.TestCase):
    """RV-01: lời gọi gán nhóm lỗi hoặc bị chặn → vẫn trả lời, mô tả lạ nằm ở khong_ro."""

    class Failing(ModelStub):
        error: Exception = ai.ModelError("Gemini không trả chữ (blockReason=SAFETY)")

        def __call__(self, system, user):
            if system.startswith(agent.LABEL_TASK):
                raise self.error
            return super().__call__(system, user)

    def run_failing(self, stub):
        tracing.begin("test")
        try:
            with mock.patch.object(agent, "call_model", stub):
                out = agent.answer("câu hỏi")
        finally:
            _, events = tracing.end()
        return out, [e["text"] for e in events if e["kind"] == "note"]

    def test_answer_is_kept_with_unclear_labels_and_a_warning(self):
        out, notes = self.run_failing(self.Failing(spend_plan(**NOVEMBER)))
        self.assertIn("Tổng chi của bạn", out["output"])
        self.assertIn(LABEL_FAILED, out["output"])
        self.assertNotIn(agent.BLOCKED, out["output"])
        txs = out["results"][0]["transactions"]
        self.assertFalse([t for t in txs if t["basis"] == "model"])
        found = warnings(notes)
        self.assertEqual(len(found), 1, notes)
        self.assertIn("blockReason=SAFETY", found[0])

    def test_grader_replay_reproduces_the_answer(self):
        out, _ = self.run_failing(self.Failing(spend_plan(**NOVEMBER)))
        trace = {
            "plan": json.dumps(agent.plan_record(out["plan"])),
            "labels": {},
            "bad_label": True,
        }
        again = grade.replay("câu hỏi", trace, "stub")
        self.assertEqual(again["output"], out["output"])

    def test_other_errors_still_escape(self):
        stub = self.Failing(spend_plan(**NOVEMBER))
        stub.error = ConnectionError("mat mang")
        with self.assertRaises(ConnectionError):
            self.run_failing(stub)

    def test_plan_call_failure_still_escapes(self):
        def broken(system, user):
            raise ai.ModelError("HTTP 500")

        with (
            mock.patch.object(agent, "call_model", broken),
            self.assertRaises(ai.ModelError),
        ):
            agent.answer("câu hỏi")


if __name__ == "__main__":
    unittest.main()
