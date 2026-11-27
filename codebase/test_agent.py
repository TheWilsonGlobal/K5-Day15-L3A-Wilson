"""Test luồng agent.py: cảnh báo trong trace, kế hoạch hỏng, che số nhạy cảm, đầu ra bị chặn, các ghi chú.
Không gọi model thật: call_model được thay bằng câu trả lời dựng sẵn. Dữ liệu dựng riêng ghi vào thư mục tạm.

    python -m unittest discover -s codebase -p "test_*.py"
"""

import contextlib
import csv
import json
import os
import random
import re
import sys
import tempfile
import unicodedata
import unittest
from collections import Counter
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["MODEL_PROVIDER"] = "fake"

import agent  # noqa: E402  # import sau khi đặt sys.path và MODEL_PROVIDER=fake
import tools  # noqa: E402  # import sau khi đặt sys.path và MODEL_PROVIDER=fake
import tracing  # noqa: E402  # import sau khi đặt sys.path và MODEL_PROVIDER=fake
from test_tools import TRUTH, ModelStub, ask, spend_plan  # noqa: E402  # import sau khi đặt sys.path

ASK_BACK = "Mình chưa hiểu chắc"
LABEL_NOTE = "cảnh báo: gán nhóm: %d/%d mục thiếu hoặc không hợp lệ, giữ khong_ro"
LABEL_FAILED = "Lần này mình chưa phân loại được các mô tả lạ"
REFUND_LINE = "hoàn tiền, tổng 189.000đ, chưa trừ vào tổng chi"
NOVEMBER = {"start": "2026-11-01", "end": "2026-11-27"}
TX_COLUMNS = [
    "tx_id",
    "user_id",
    "date",
    "time",
    "amount_vnd",
    "direction",
    "channel",
    "description",
]


def traced(plan, **kwargs):
    """→ (kết quả, stub, các dòng note trong trace)."""
    tracing.begin("test")
    try:
        out, stub = ask(plan, **kwargs)
    finally:
        _, events = tracing.end()
    return out, stub, [e["text"] for e in events if e["kind"] == "note"]


def warnings(notes):
    return [n for n in notes if n.startswith("cảnh báo")]


def row(tx_id, amount, description, date="2026-11-10", time="10:00", direction="out"):
    return {
        "tx_id": tx_id,
        "user_id": "U001",
        "date": date,
        "time": time,
        "amount_vnd": amount,
        "direction": direction,
        "channel": "the",
        "description": description,
    }


@contextlib.contextmanager
def statement(*rows):
    """Sao kê dựng riêng: file CSV thật trong thư mục tạm, công cụ đọc nó qua TX_PATH."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "transactions.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, TX_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        with mock.patch.object(tools, "TX_PATH", path):
            yield


class TestChoiceFallback(unittest.TestCase):
    """E7: reason / missing thiếu hoặc sai kiểu → mặc định, và ghi cảnh báo vào trace."""

    CASES = (
        ("tu_choi", "reason", "ngoai_pham_vi", agent.REFUSALS),
        ("hoi_lai", "missing", "noi_dung", agent.QUESTIONS),
    )
    BAD: tuple[object, ...] = ([], {}, ["dau_tu"], {"a": 1}, 7, True, None, "linh_tinh")

    def check(self, plan, key, default, texts):
        out, _, notes = traced(plan)
        self.assertEqual(out["plan"][key], default)
        self.assertIn(texts[default], out["output"])
        self.assertNotRegex(out["output"], r"\d")
        found = warnings(notes)
        self.assertEqual(len(found), 1, notes)
        self.assertTrue(found[0].startswith("cảnh báo: %s = " % key), found[0])
        self.assertIn(default, found[0])
        return found[0]

    def test_invalid_or_wrong_type_value_falls_back_with_warning(self):
        for intent, key, default, texts in self.CASES:
            for value in self.BAD:
                with self.subTest(intent=intent, value=value):
                    note = self.check(
                        {"intent": intent, key: value}, key, default, texts
                    )
                    self.assertIn(repr(value), note)

    def test_absent_value_falls_back_with_warning(self):
        for intent, key, default, texts in self.CASES:
            with self.subTest(intent=intent):
                self.assertIn(
                    "None", self.check({"intent": intent}, key, default, texts)
                )

    def test_long_raw_value_is_cut_in_the_note(self):
        note = self.check(
            {"intent": "tu_choi", "reason": "z" * 5000},
            "reason",
            "ngoai_pham_vi",
            agent.REFUSALS,
        )
        self.assertLess(len(note), 160)

    def test_valid_values_write_no_warning(self):
        plans = [{"intent": "tu_choi", "reason": r} for r in agent.REFUSALS]
        plans += [{"intent": "hoi_lai", "missing": m} for m in agent.QUESTIONS]
        for plan in plans:
            with self.subTest(plan=plan):
                _, _, notes = traced(plan)
                self.assertEqual(warnings(notes), [])


class TestLabelWarning(unittest.TestCase):
    """E8: nhãn thiếu hoặc ngoài danh sách → giữ khong_ro, trace ghi N/M."""

    def run_labels(self, make_reply):
        """make_reply(items) → đối tượng nhãn model trả. → (kết quả, số mục đã gửi, notes)."""

        class Labeller(ModelStub):
            sent = 0

            def __call__(self, system, user):
                if system.startswith(agent.LABEL_TASK):
                    items = json.loads(user)
                    Labeller.sent = len(items)
                    return {
                        "text": json.dumps(make_reply(items)),
                        "model": "stub",
                        "tokens_in": 1,
                        "tokens_out": 1,
                    }
                return super().__call__(system, user)

        tracing.begin("test")
        with mock.patch.object(agent, "call_model", Labeller(spend_plan(**NOVEMBER))):
            out = agent.answer("câu hỏi")
        _, events = tracing.end()
        self.assertGreaterEqual(Labeller.sent, 2)
        return out, Labeller.sent, [e["text"] for e in events if e["kind"] == "note"]

    def test_all_missing_or_invalid(self):
        replies = {
            "empty": lambda items: {},
            "outside list": lambda items: {i["id"]: "dau_tu" for i in items},
            "list value": lambda items: {i["id"]: ["an_uong"] for i in items},
        }
        for name, reply in replies.items():
            with self.subTest(name):
                out, sent, notes = self.run_labels(reply)
                self.assertEqual(warnings(notes), [LABEL_NOTE % (sent, sent)])
                self.assertFalse(
                    [
                        t
                        for t in out["results"][0]["transactions"]
                        if t["basis"] == "model"
                    ]
                )

    def test_partly_invalid_counts_only_bad_items_and_keeps_them_unclear(self):
        def reply(items):
            labels = {i["id"]: "mua_sam" for i in items}
            del labels[items[0]["id"]]
            labels[items[1]["id"]] = "khong_co_nhom_nay"
            return labels

        out, sent, notes = self.run_labels(reply)
        self.assertEqual(warnings(notes), [LABEL_NOTE % (2, sent)])
        txs = out["results"][0]["transactions"]
        self.assertTrue(any(t["basis"] == "model" for t in txs))
        self.assertTrue(
            all(t["category"] in tools.CATEGORIES for t in txs)
        )  # nhãn lạ không lọt vào
        self.assertTrue(
            any(t["basis"] == "can_model" and t["category"] == "khong_ro" for t in txs)
        )

    def test_fully_valid_reply_writes_no_warning(self):
        _, _, notes = self.run_labels(
            lambda items: {i["id"]: "khong_ro" for i in items}
        )
        self.assertEqual(warnings(notes), [])


class TestBrokenPlan(unittest.TestCase):
    def assert_ask_back(self, plan):
        out, stub, notes = traced(plan)
        self.assertIn(ASK_BACK, out["output"])
        self.assertEqual(
            (out["plan"], out["results"], out["draft"]),
            ({"intent": "hoi_lai"}, [], None),
        )
        self.assertEqual(len(stub.calls), 1)
        self.assertIn("dừng: kế hoạch không hợp lệ, hỏi lại", notes)

    def test_json_array_plan_asks_back(self):
        one = json.dumps(spend_plan())
        for plan in ("[%s]" % one, "[%s, %s]" % (one, one), "```json\n[%s]\n```" % one):
            with self.subTest(plan=plan[:30]):
                self.assert_ask_back(plan)

    def test_deeply_nested_json_asks_back(self):
        for plan in (
            '{"intent":' + "[" * 100000 + "]" * 100000 + "}",
            '{"a":' * 100000 + "1" + "}" * 100000,
        ):
            with self.subTest(plan=plan[:20]):
                self.assert_ask_back(plan)

    def test_two_objects_and_broken_json_are_rejected(self):
        one = json.dumps(spend_plan())
        for text in (one + " " + one, "{khong phai json}", "", None):
            self.assertIsNone(agent.parse_json(text), text)
        self.assertEqual(agent.parse_json('Đây: {"x": [1, 2]} hết'), {"x": [1, 2]})

    def test_month_year_zero_is_not_a_month(self):
        self.assertIsNone(agent._month("0000-01"))
        self.assertEqual(agent._month("0001-01"), (1, 1))
        for plan in (
            {"intent": "so_sanh", "m1": "0000-01", "m2": "2026-11"},
            {"intent": "so_sanh", "m1": "2026-10", "m2": "0000-12"},
        ):
            with self.subTest(plan=plan):
                self.assert_ask_back(plan)

    def test_bad_fields_ask_back(self):
        for plan in (
            spend_plan(start="hom qua"),
            spend_plan(start=20261001),
            spend_plan("noi_ban"),
            spend_plan("noi_ban", merchant="xe"),
            spend_plan("noi_ban", merchant=123),
            {"intent": "so_sanh", "m1": "2026-13", "m2": "2026-10"},
            {"intent": "so_sanh", "m1": "2026-10"},
        ):
            with self.subTest(plan=plan):
                self.assert_ask_back(plan)


class TestMasking(unittest.TestCase):
    def assert_masked(self, text, *secrets):
        masked, flag = agent.mask_sensitive(text)
        self.assertTrue(flag, text)
        self.assertIn("[đã che]", masked)
        for secret in secrets:
            self.assertNotIn(secret, masked, text)

    def test_separated_digit_runs_are_masked(self):
        for secret in (
            "0912 345 678",
            "0912.345.678",
            "0912-345-678",
            "3782 822463 10005",
            "3782-822463-10005",
            "1903.4567.8901.2",
            "4111.1111.1111.1111",
            "123456789",
            "1234567890123456789",
        ):
            with self.subTest(secret=secret):
                self.assert_masked("số của mình " + secret + " nhé", secret)
                self.assertNotRegex(agent.mask_sensitive("số " + secret)[0], r"\d")

    def test_otp_before_and_after_keyword(self):
        self.assert_masked("482913 la ma OTP cua minh", "482913")
        self.assert_masked("482913 là mã xác nhận", "482913")
        self.assert_masked("OTP: 48 29 13", "48 29 13", "29 13")
        self.assert_masked("mã xác thực 48-29-13", "48-29-13", "29-13")
        self.assert_masked("cvv 123", "123")
        self.assert_masked("ngày 27/11/2026 mã OTP 482913", "482913")
        self.assertIn(
            "27/11/2026", agent.mask_sensitive("ngày 27/11/2026 mã OTP 482913")[0]
        )

    def test_password_token_with_a_digit_is_masked_whole(self):
        for text in (
            "mật khẩu của mình là Abc12345 nhé",
            "mat khau Abc12345",
            "Mật khẩu: p@ss9word!",
        ):
            with self.subTest(text=text):
                self.assert_masked(text, "Abc", "12345", "p@ss", "word")

    def test_digit_run_length_limits(self):
        for text in (
            "12345678",
            "1234 5678",
            "12345678901234567890",
        ):  # 8 và 20 chữ số: không phải số thẻ/tài khoản
            with self.subTest(text=text):
                self.assertEqual(
                    agent.mask_sensitive("mã " + text), ("mã " + text, False)
                )

    def test_money_and_dates_are_kept(self):
        for text in (
            "500.000đ",
            "1.275.000đ",
            "12.345.678.901đ",
            "150.000.000 VNĐ",
            "150 000đ",
            "27/11/2026",
            "2026-11-01",
            "27-11-2026",
            "27.11.2026",
            "500.000 đ cho pin",
            "từ 2026-11-01 đến 27/11/2026 trên 500.000",
            "pin từ 27-11-2026",
            "cvv 27.11.2026",
            "150000 đ cho pin",
            "500 nghìn nạp pin",
        ):
            with self.subTest(text=text):
                self.assertEqual(agent.mask_sensitive(text), (text, False))

    def test_dong_unit_keeps_the_amount(self):
        for text in (
            "thu nhập 1.500.000.000 đồng",
            "vay 150.000.000.000 đồng",
            "150.000.000 VND",
        ):
            with self.subTest(text=text):
                self.assertEqual(agent.mask_sensitive(text), (text, False))

    def test_nine_digit_unbroken_amounts_are_masked(self):
        # Quyết định PM (X3): chuỗi liền ≥ 9 chữ số không được miễn tiền, kể cả khi có đơn vị đứng sau
        # («stk 0123456789 dong» là bắt buộc che). Thay cho các ca «150000000 đ/dong/...» từng được giữ.
        for text in (
            "150000000 đ",
            "150000000 nghìn",
            "150000000 nghin",
            "150000000 triệu",
            "150000000 trieu",
            "150000000 vnd",
            "150 000 000 VNĐ",
            "150000000 dong",
            "150000000 vnđ",
        ):
            with self.subTest(text=text):
                masked, flag = agent.mask_sensitive(text)
                self.assertTrue(flag, text)
                self.assertNotRegex(masked, r"\d")
        self.assertEqual(
            agent.mask_sensitive("thu nhập 1.500.000.000 đồng, số 0912 345 678")[0],
            "thu nhập 1.500.000.000 đồng, số [đã che]",
        )
        self.assertEqual(
            agent.mask_sensitive("vay 150.000.000.000 đồng, stk 3782-822463-10005")[0],
            "vay 150.000.000.000 đồng, stk [đã che]",
        )

    def test_decomposed_dong_unit_keeps_the_amount(self):
        text = unicodedata.normalize("NFD", "thu nhập 1.500.000.000 đồng")
        self.assertEqual(agent.mask_sensitive(text), (text, False))

    def test_password_keyword_keeps_following_date_or_amount(self):
        for text in (
            "Quên mật khẩu, hôm 27/11/2026 mình tiêu gì?",
            "mật khẩu 27-11-2026",
        ):
            with self.subTest(text=text):
                self.assertEqual(agent.mask_sensitive(text), (text, False))
        self.assert_masked("mat khau Abc12345", "Abc", "12345")
        self.assert_masked("mật khẩu Abc12345 đồng", "Abc", "12345")

    def test_floor_masks_numbers_right_after_secret_keyword(self):
        # Quyết định PM (phương án C, 27/11/2026): sàn HEAD thắng, fail-safe. Số ngay sau từ khoá bí mật luôn bị che.
        for text, expected in (
            ("OTP 500 nghìn", "OTP [đã che] nghìn"),
            ("OTP ngày 2026-11-01", "OTP ngày [đã che]-11-01"),
            (
                "quên mật khẩu, khoản 500.000 đồng",
                "quên mật khẩu, khoản [đã che].[đã che] đồng",
            ),
            (
                "đổi mật khẩu rồi, khoản 500.000đ là gì",
                "đổi mật khẩu rồi, khoản [đã che] là gì",
            ),
            (
                "quên mật khẩu, khoản >500.000",
                "quên mật khẩu, khoản >[đã che].[đã che]",
            ),
            ("quên mật khẩu, 100-200k", "quên mật khẩu, [đã che]"),
            ("mật khẩu lỗi, tiêu 200k là gì", "mật khẩu lỗi, tiêu [đã che] là gì"),
            ("quên mật khẩu, mã T0173 là gì", "quên mật khẩu, mã T[đã che] là gì"),
        ):
            with self.subTest(text=text):
                self.assertEqual(agent.mask_sensitive(text), (expected, True))

    def test_separated_secret_never_reaches_the_model(self):
        out, stub = ask(spend_plan(), text="stk 1903.4567.8901.2, 482913 la OTP")
        self.assertTrue(stub.calls)
        for _, user in stub.calls:
            self.assertNotIn("1903.4567", user)
            self.assertNotIn("482913", user)
        self.assertEqual(stub.calls[0][1], "stk [đã che], [đã che] la OTP")
        self.assertIn(agent.SENSITIVE_WARNING, out["output"])

    def test_question_is_capped_at_1000_characters(self):
        _, stub = ask(spend_plan(), text="  " + "a" * 1500 + "  ")
        self.assertEqual(stub.calls[0][1], "a" * 1000)


#: Bộ ca cố định của X3. MUST_MASK: không còn chữ số nào trong đầu ra. MUST_KEEP: giữ nguyên, không có cảnh báo.
MUST_MASK = (
    "so the 4111111111111111 2027",
    "the 4111 1111 1111 1111 2027",
    "the 4111 1111 1111 1111 12 26",
    "the 4111 1111-1111 1111",
    "stk 1903 4567 8901 2345 6789",
    "stk 0123456789 dong a bank",
    "0912 345 678",
    "0912.345.678",
    "3782 822463 10005",
    "3782-822463-10005",
    "1903.4567.8901.2",
    "482913 la ma OTP cua minh",
    "OTP: 48 29 13",
    "mat khau Abc12345",
    "mật khẩu của mình là Abc12345",
    # X3b (CR3-01/02/03): từ khoá dính liền, từ khoá + số ngắn, năm, tiền dính từ khoá, số có dấu chấm
    "otp482913",
    "pin1234",
    "cvv123",
    "mật khẩu123456",
    "otp_482913",
    "pincode 1234",
    "OTPcode: 482913",
    "mã OTPs 482913",
    "PIN2 123456",
    "otp 482913 k nhận được",
    "pin 4829 k dùng được",
    "mật khẩu 482913 k đúng",
    "OTP 482913 K",
    "otp 482913 tr",
    "otp 482913 dong y",
    "otp 482913đ",
    "OTP: 482.913",
    "pin 2024",
    "mã pin của mình là 1999",
    "otp 2025",
    "cvv 2027",
    "mật khẩu 2024",
    "otp 12 3456",
    "otp 11 2026",
)
MUST_KEEP = (
    "Quên mật khẩu, tháng 10 mình tiêu bao nhiêu?",
    "Quên mật khẩu, hôm 27/11/2026 mình tiêu gì?",
    "hôm 27/11/2026, mình tiêu gì",
    "ngày 2/11",
    "từ 01/11 đến 15/11",
    "hôm 2/11/2026",
    "(tháng 11/2026)",
    "xem 5 khoản lớn nhất",
    "tiêu 2tr",
    "khoản 500.000đ, là gì",
    "năm 2026 mình quên mã pin",
    "otp lỗi, tiêu từ 01.11 đến 27.11",
    "khoản 150.000.000 là gì",
    "tiêu trên 1.500.000.000",
    "thu nhập 1.500.000.000 đồng",
    "vay 150.000.000.000 đồng",
    "500 nghìn",
    "1.275.000đ",
    "2026-11-01",
    "12.345.678.901đ",
    # X3b (CR3-04/05): ngày, khoảng ngày, tháng, tiền, khoảng tiền đứng sau từ khoá mật khẩu; giữ nguyên
    "quên mật khẩu, tiêu (2/11/2026) gì",
    "tiêu (2/11/2026) gì",
    "(11/2026)",
    "ngày:2/11/2026",
    '"27/11/2026"',
    "quên mật khẩu, tiêu (11/2026)",
    "quên mật khẩu, từ 01/11-15/11",
    "quên mật khẩu, từ 01/11–15/11",
    "quên mật khẩu, tiêu 01.11-15.11",
    "quên mật khẩu, tháng10 tiêu gì",
    "quên mật khẩu, T11/2026",
    "quên mật khẩu, khoản ~2tr",
    "quên mật khẩu, 2tr5 là gì",
    "quên mật khẩu, 1,5tr vào đâu",
    "quên mật khẩu, 1.500.000 đồng",
    "quên mật khẩu, 1.500.000đ",
    "tháng 10 2026 100000 trở lên",
    "từ 100000-200000",
    "từ 100000 200000",
    "từ 1000000-2000000",
    "mua pin 1,500,000 đ",
)
#: Các đầu vào masking đã có trong test (test_tools HEAD + các ca ở trên) — dùng cho kiểm superset.
EXISTING_MASKING = (
    "OTP của mình là 482913, số thẻ 4111 1111 1111 1111, tk 0123456789",
    "OTP 482913 tổng chi",
    "ngày 27/11/2026 mã OTP 482913",
    "482913 là mã xác nhận",
    "mã xác thực 48-29-13",
    "cvv 123",
    "mật khẩu của mình là Abc12345 nhé",
    "mat khau Abc12345",
    "Mật khẩu: p@ss9word!",
    "mật khẩu Abc12345 đồng",
    "stk 1903.4567.8901.2, 482913 la OTP",
)
# Regex của HEAD (agent.py trước X3), copy làm bộ tham chiếu superset: mọi chuỗi HEAD che phải vẫn bị che.
HEAD_KW = re.compile(
    r"(?i)\b(otp|mật khẩu|mat khau|mã xác (?:nhận|thực)|pin|cvv)(\D{0,30}?)(\d{3,8})"
)
HEAD_CARD = re.compile(r"(?<!\d)(?:(?:\d{4}[ -]){2,4}\d{1,4}|\d{9,19})(?!\d)")


def head_masked_digits(text):
    found = [m.group(3) for m in HEAD_KW.finditer(text)]
    return found + [re.sub(r"\D", "", m.group(0)) for m in HEAD_CARD.finditer(text)]


class TestMaskingCorpus(unittest.TestCase):
    def test_must_mask(self):
        for text in MUST_MASK:
            with self.subTest(text=text):
                masked, flag = agent.mask_sensitive(text)
                self.assertTrue(flag, text)
                self.assertIn("[đã che]", masked)
                self.assertNotRegex(masked, r"\d", text)

    def test_must_keep(self):
        for text in MUST_KEEP:
            with self.subTest(text=text):
                self.assertEqual(agent.mask_sensitive(text), (text, False))

    def test_head_masked_inputs_are_still_masked(self):
        checked = 0
        for text in MUST_MASK + EXISTING_MASKING:
            digits = head_masked_digits(text)
            if not digits:
                continue
            checked += 1
            with self.subTest(text=text):
                masked, flag = agent.mask_sensitive(text)
                self.assertTrue(flag, text)
                for d in digits:
                    self.assertNotIn(d, masked, text)
        self.assertGreater(checked, 5)  # bộ tham chiếu HEAD phải thực sự có ca để so


#: Đầu vào của các probe R3 (probe.py, probe2.py), lấy nguyên văn: đầu vào cho kiểm superset.
R3_PROBE_INPUTS = (
    "so the 4111111111111111 2027",
    "the 4111 1111 1111 1111 2027",
    "the 4111 1111 1111 1111 12 26",
    "the 4111 1111-1111 1111",
    "the 4111-1111 1111-1111",
    "the 4111111111111111 123",
    "stk 0123456789 dong a bank",
    "stk 1234567890123 500000",
    "Quên mật khẩu, tháng 10 mình tiêu bao nhiêu?",
    "đổi mật khẩu rồi, ngày 2/11 tiêu gì",
    "đổi mật khẩu rồi, tiêu từ 01/11 đến 15/11",
    "quên mật khẩu (tháng 11/2026) tiêu gì",
    "mật khẩu lỗi, xem 5 khoản lớn nhất",
    "đổi mật khẩu, tiêu 2tr là gì",
    "năm 2026 mình quên mã pin",
    "otp lỗi, tiêu từ 01.11 đến 27.11",
    "khoản 150.000.000 là gì",
    "tiêu trên 1.500.000.000",
    "otp482913",
    "OTP482913 la gi",
    "pin1234",
    "mã pin1234",
    "cvv123",
    "mật khẩu123456",
    "otp_482913",
    "OTP là482913",
    "otp 482913 k nhận được",
    "pin 4829 k dùng được",
    "mật khẩu 482913 k đúng",
    "otp 482913 k",
    "otp 482913 dong y chuyen",
    "otp 482913 đồng ý",
    "otp 482913 tr",
    "OTP: 482.913",
    "mã otp 482.913",
    "otp 482913đ",
    "mật khẩu là 123456 nghìn lần sai",
    "pin 2024",
    "mã pin của mình là 1999",
    "otp 2025",
    "mật khẩu 2024",
    "cvv 2027",
    "otp 12 3456",
    "otp 11 2026",
    "pin 2.024",
    "otp 48-29-13",
    "otp 12.11.2026",
    "otp 48/29/13",
    "otp 482/913",
    "stk: 0123456789",
    "số tài khoản 19034567890123",
    "số tài khoản: 1903 456 789 012",
    "số tài khoản 190.345.678.901",
    "stk: 1903-456789-012",
    "(4111 1111 1111 1111)",
    "thẻ (4111.1111.1111.1111) hết hạn 12/27",
    "thẻ 4111.1111.1111.1111 12/27 cvv 123",
    "4111-1111-1111-1111 exp 12/27",
    "4111 1111.1111 1111",
    "4111.1111 1111.1111",
    "4111  1111  1111  1111",
    "4111\xa01111\xa01111\xa01111",
    "4111\u30001111\u30001111\u30001111",
    "4111–1111–1111–1111",
    "4111_1111_1111_1111",
    "4111/1111/1111/1111",
    "4111, 1111, 1111, 1111",
    "４１１１１１１１１１１１１１１１",
    "４１１１ １１１１ １１１１ １１１１",
    "OTP ４８２９１３",
    "số tài khoản 0123456789",
    "mật khẩu: Abc12345",
    "mã xác nhận 482913",
    "mật khẩu của mình là Abc12345",
    "mật khẩu:Abc12345",
    "mật khẩu=Abc12345",
    "pass: Abc12345",
    "mk Abc12345",
    "mật khẩu là abcdefgh",
    "mật khẩu a1",
    "mật khẩu 12345",
    "mật khẩu mới của tài khoản ngân hàng mà mình vừa đổi hôm qua là Abc12345",
    "mật khẩu 11/2026abc",
    "mật khẩu: 27/11/2026",
    "4111 1111-1111 1111 12 26",
    "số điện thoại 0912 345 678",
    "0912-345-678",
    "+84 912 345 678",
    "cccd 001099012345",
    "stk 12345678901234567890",
    "otp của mình, được gửi lúc sáng nay, là 482913",
    "ngày 27/11/2026",
    "27-11-2026",
    "27.11",
    "tháng 11/2026",
    "tháng 2026-11",
    "từ 01/11 đến 15/11",
    "từ 01/11-15/11",
    "01/11/2026 - 15/11/2026",
    "2026-11-01 2026-11-15",
    "2026-11-01 đến 2026-11-30",
    "từ 1 đến 15",
    "5 khoản",
    "top 10 khoản",
    "2 triệu",
    "1,5tr",
    "200k",
    "1.500.000 đồng",
    "1.500.000đ",
    "1,500,000 đ",
    "1 500 000 đồng",
    "150 000 000 đồng",
    "150 000 000 VNĐ",
    "20000000đ",
    "trên 100000000 đồng",
    "từ 100.000 đến 200.000",
    "từ 100000-200000",
    "từ 100000 - 200000",
    "khoản 100000 200000",
    "từ 1000000-2000000",
    "các khoản 500000-1000000",
    "100-200k",
    "tháng 9 10 11",
    "tháng 10 2026 100000 trở lên",
    "mã T0173",
    "đổi T0173 sang ăn uống",
    "1500000",
    "123456789 là gì",
    "mật khẩu lỗi, tiêu 1,5tr vào đâu",
    "mật khẩu lỗi, tiêu 200k là gì",
    "quên mật khẩu, tiêu (2/11/2026) gì",
    "quên mật khẩu, tiêu (11/2026)",
    "quên mật khẩu, từ 01/11-15/11",
    "quên mật khẩu, từ 01/11–15/11",
    "quên mật khẩu, ngày:2/11/2026",
    "quên mật khẩu, tháng10 tiêu gì",
    "quên mật khẩu, T11/2026",
    "quên mật khẩu, khoản >500.000",
    "quên mật khẩu, khoản ~2tr",
    "quên mật khẩu, 100-200k",
    "quên mật khẩu, 2tr5 là gì",
    "quên mật khẩu, tiêu 01.11-15.11",
    "quên mật khẩu, 2 triệu",
    "quên mật khẩu, 1.500.000 đồng",
    'quên mật khẩu, "27/11/2026"',
    "quên mật khẩu, “1.500.000đ”",
    "mua sạc pin 150000 là gì",
    "mua pin 500.000đ",
    "pin hỏng, tiêu 500 nghìn",
    "đổi pin 350k",
    "otp lỗi ngày 27/11",
    "tiêu mua pin từ 100-200 nghìn",
    "mua pin 1,500,000 đ",
    "khoản 1.500.000 đồng",
    "quên mật khẩu, 500 nghìn",
    "mật khẩu123456 của mình",
    "pincode 1234",
    "OTPcode: 482913",
    "PIN2 123456",
    "mã OTPs 482913",
    "OTP 482913 K",
    "otp 482913 dong y",
    "4111 1111-1111-1111 12 26",
    "4111 1111 1111 1111 12 26",
    "stk 190.345.678.901",
    "quên mật khẩu, mã T0173 là gì",
)


def head_mask_sensitive(text):
    """Bản sao nguyên văn mask_sensitive của HEAD (trước X3b), làm tham chiếu cho kiểm superset."""
    masked = re.sub(
        r"(?i)\b(otp|mật khẩu|mat khau|mã xác (?:nhận|thực)|pin|cvv)(\D{0,30}?)\d{3,8}",
        r"\1\2[đã che]",
        text,
    )
    masked = re.sub(
        r"(?<!\d)(?:(?:\d{4}[ -]){2,4}\d{1,4}|\d{9,19})(?!\d)", "[đã che]", masked
    )
    return masked, masked != text


#: Nguyên tử cho bộ sinh ngẫu nhiên: từ khoá, nhóm số có dấu, ngày, đơn vị tiền, chữ tiếng Việt.
RANDOM_ATOMS = (
    "otp",
    "OTP",
    "pin",
    "cvv",
    "mật khẩu",
    "mat khau",
    "mã xác nhận",
    "stk",
    " ",
    " ",
    " ",
    ": ",
    " là ",
    "-",
    ".",
    "/",
    "đ",
    " đ",
    "k",
    " k",
    " dong",
    " đồng ý",
    "tr",
    "482913",
    "123",
    "2026",
    "12",
    "1111",
    "4111",
    "0123456789",
    "500.000",
    "a",
    ",",
    "(",
    "T0173",
    "01/11",
    "-15/11",
    "tháng ",
    "100000",
    "200k",
    " nghìn",
    "2025",
    "pin ",
    "OTPs",
    "0912",
    "345",
    "678",
)
RANDOM_SEED = 20260
RANDOM_COUNT = 20000


class TestMaskingSupersetOfHead(unittest.TestCase):
    """Sàn: mọi chữ số HEAD che vẫn vắng mặt trong đầu ra mới, và đầu ra mới không có chữ số nào
    mà đầu vào không có. Chữ số đếm theo chuỗi \\d+ liền nhau."""

    def assert_superset(self, text):
        head_out = head_mask_sensitive(text)[0]
        new_out = agent.mask_sensitive(text)[0]
        head_tokens = Counter(re.findall(r"\d+", head_out))
        new_tokens = Counter(re.findall(r"\d+", new_out))
        input_tokens = Counter(re.findall(r"\d+", text))
        for token, count in new_tokens.items():
            self.assertLessEqual(count, head_tokens[token], (text, token))
        for token in input_tokens:
            if head_tokens[token] == 0:
                self.assertEqual(new_tokens[token], 0, (text, token))
        if head_out != text:
            self.assertNotEqual(new_out, text, text)
        return head_out != text

    def test_corpus_and_r3_probe_inputs(self):
        checked = 0
        for text in MUST_MASK + MUST_KEEP + EXISTING_MASKING + R3_PROBE_INPUTS:
            with self.subTest(text=text):
                self.assert_superset(text)
                checked += 1
        self.assertGreater(checked, 150)

    def test_seeded_random_strings_are_a_superset(self):
        rng = random.Random(RANDOM_SEED)
        head_masked = 0
        for _ in range(RANDOM_COUNT):
            text = "".join(rng.choice(RANDOM_ATOMS) for _ in range(rng.randint(2, 8)))
            head_masked += self.assert_superset(text)
        self.assertGreater(
            head_masked, 1000
        )  # HEAD phải thực sự che nhiều ca, nếu không kiểm này rỗng


class TestSecretPhrasesThroughAnswer(unittest.TestCase):
    def test_secret_digits_never_reach_the_model_and_warn(self):
        for text, secret in (
            ("mã pin1234 của mình bị lộ", "1234"),
            ("otp 482913 k nhận được", "482913"),
        ):
            with self.subTest(text=text):
                out, stub = ask(spend_plan(), text=text)
                self.assertTrue(stub.calls)
                self.assertIn("[đã che]", stub.calls[0][1])
                for _, user in stub.calls:
                    self.assertNotIn(secret, user)
                self.assertIn(agent.SENSITIVE_WARNING, out["output"])


class TestMaskingThroughAnswer(unittest.TestCase):
    def test_model_never_receives_masked_digits(self):
        masked_inputs = (
            "stk 1903 4567 8901 2345 6789",
            "OTP: 48 29 13",
            "mật khẩu của mình là Abc12345",
        )
        kept_inputs = (
            "Quên mật khẩu, tháng 10 mình tiêu bao nhiêu?",
            "khoản 150.000.000 là gì",
            "otp lỗi, tiêu từ 01.11 đến 27.11",
        )
        for text in masked_inputs:
            with self.subTest(text=text):
                out, stub = ask(spend_plan(), text=text)
                sent = stub.calls[0][1]
                self.assertNotRegex(sent, r"\d")
                self.assertIn(agent.SENSITIVE_WARNING, out["output"])
        for text in kept_inputs:
            with self.subTest(text=text):
                out, stub = ask(spend_plan(), text=text)
                self.assertEqual(stub.calls[0][1], text)
                self.assertNotIn(agent.SENSITIVE_WARNING, out["output"])


class TestBlockedOutput(unittest.TestCase):
    def test_guillemet_in_large_transaction_is_not_blocked(self):
        with statement(row("T0001", 6000000, "DIENMAY » 55 « 77")):
            out, _ = ask(spend_plan(**NOVEMBER), label_reply="{}")
        self.assertNotIn(agent.BLOCKED, out["output"])
        self.assertIn("- Khoản lớn: T0001 6.000.000đ «DIENMAY  55  77».", out["output"])

    def test_large_transaction_note_threshold(self):
        with statement(
            row("T0001", tools.LARGE_VND, "SHOPVUI A"),
            row("T0002", tools.LARGE_VND - 1, "SHOPVUI B"),
        ):
            out, _ = ask(spend_plan(**NOVEMBER))
        self.assertIn("- Khoản lớn: T0001 5.000.000đ", out["output"])
        self.assertNotIn("Khoản lớn: T0002", out["output"])

    def test_blocked_output_keeps_both_warnings(self):
        real = agent._notes
        with mock.patch.object(
            agent, "_notes", lambda s: real(s) + ["Bạn còn dư 123.456đ"]
        ):
            out, stub = ask(
                spend_plan(), label_reply="xin lỗi", text="OTP 482913 tổng chi"
            )
        self.assertEqual(len(stub.calls), 2)
        lines = out["output"].split("\n")
        self.assertEqual(lines[0], agent.BLOCKED)
        self.assertEqual(len(lines), 3, lines)
        self.assertTrue(lines[1].startswith(LABEL_FAILED))
        self.assertEqual(lines[2], agent.SENSITIVE_WARNING)
        self.assertNotIn("123.456", out["output"])

    def test_blocked_draft_is_cleared(self):
        tx_id = next(t["tx_id"] for t in TRUTH.values() if t["tag"] == "mo_ta_mo_ho")
        real = agent._line
        with mock.patch.object(agent, "_line", lambda tx: real(tx) + " 999.999đ"):
            out, _ = ask(
                {"intent": "sua_nhom", "tx_id": tx_id, "new_category": "mua_sam"}
            )
        self.assertEqual(out["output"], agent.BLOCKED)
        self.assertIsNone(out["draft"])


class TestPlanRewrite(unittest.TestCase):
    def test_total_with_a_category_becomes_a_category_question(self):
        plan = agent.validate_plan(spend_plan("tong_chi", category="an_uong"))
        self.assertEqual((plan["intent"], plan["category"]), ("theo_nhom", "an_uong"))


class TestRecategorizePlan(unittest.TestCase):
    def test_malformed_tx_id_asks_which_transaction(self):
        for tx_id in (
            "T12",
            "T00001",
            "0214",
            "TT214",
            "T021A",
            "T0214; T0215",
            "",
            None,
            214,
            ["T0214"],
        ):
            with self.subTest(tx_id=tx_id):
                out, _ = ask(
                    {"intent": "sua_nhom", "tx_id": tx_id, "new_category": "mua_sam"}
                )
                self.assertEqual(
                    (out["plan"]["intent"], out["plan"].get("missing")),
                    ("hoi_lai", "giao_dich"),
                )
                self.assertIsNone(out["draft"])

    def test_tx_id_is_trimmed_and_uppercased(self):
        plan = agent.validate_plan(
            {"intent": "sua_nhom", "tx_id": " t0214 ", "new_category": "mua_sam"}
        )
        self.assertEqual(plan["tx_id"], "T0214")

    def test_unknown_new_category_asks_for_category(self):
        out, _ = ask({"intent": "sua_nhom", "tx_id": "T0214", "new_category": "vang"})
        self.assertEqual(out["plan"]["missing"], "nhom")
        self.assertIsNone(out["draft"])


class TestNotesAndNotices(unittest.TestCase):
    def test_refund_note_shows_only_with_total_spend_lines(self):
        shown = [
            spend_plan(**NOVEMBER),
            spend_plan("nhieu_nhat", **NOVEMBER),
            spend_plan("liet_ke", **NOVEMBER),
        ]
        hidden = [
            spend_plan("liet_ke", category="mua_sam", **NOVEMBER),
            spend_plan("theo_nhom", category="mua_sam", **NOVEMBER),
            spend_plan("noi_ban", merchant="shopvui", **NOVEMBER),
            {"intent": "so_sanh", "m1": "2026-10", "m2": "2026-11"},
        ]
        for plan in shown:
            with self.subTest(plan=plan):
                self.assertIn(REFUND_LINE, ask(plan)[0]["output"])
        for plan in hidden:
            with self.subTest(plan=plan):
                output = ask(plan)[0]["output"]
                self.assertNotIn("hoàn tiền", output)
                self.assertNotIn(agent.BLOCKED, output)

    def test_duplicate_note_names_both_transactions(self):
        out, _ = ask(spend_plan(**NOVEMBER))
        self.assertIn("- Nghi trừ trùng: T0214, T0215 giống hệt nhau", out["output"])

    def unclear_output(self, unclear):
        with statement(
            row("T0001", 100000, "BEPMAY FOOD"), row("T0002", unclear, "CK 123456")
        ):
            return ask(spend_plan("nhieu_nhat", **NOVEMBER))[0]["output"]

    def test_unclear_larger_than_top_category_warns(self):
        output = self.unclear_output(100001)
        self.assertIn("phần chưa rõ nhóm còn lớn hơn nhóm này (100.001đ)", output)
        self.assertNotIn(agent.BLOCKED, output)

    def test_unclear_not_larger_does_not_warn(self):
        for amount in (100000, 99999):
            self.assertNotIn("còn lớn hơn nhóm này", self.unclear_output(amount))

    def test_nothing_classifiable_says_so(self):
        with statement(row("T0001", 100000, "CK 123456")):
            out, _ = ask(spend_plan("nhieu_nhat", **NOVEMBER))
        self.assertIn("chưa khoản chi nào đủ căn cứ để xếp nhóm", out["output"])

    def test_table_is_limited_to_the_largest_rows(self):
        rows = [
            row("T%04d" % i, i * 1000, "BEPMAY %d" % i, date="2026-11-%02d" % i)
            for i in range(1, agent.TABLE_LIMIT + 4)
        ]
        with statement(*rows):
            out, _ = ask(spend_plan("liet_ke", **NOVEMBER))
        listed = [
            line.split()[0]
            for line in out["output"].split("\n")
            if line.startswith("  T")
        ]
        self.assertEqual(listed, ["T%04d" % i for i in range(13, 3, -1)])

    def test_range_partly_outside_data_says_so(self):
        out, _ = ask(spend_plan(start="2026-11-01", end="2026-11-30"))
        self.assertIn("Dữ liệu chỉ có từ", out["output"])
        self.assertNotIn("Dữ liệu chỉ có từ", ask(spend_plan())[0]["output"])

    def test_empty_period_and_empty_category(self):
        with statement(
            row("T0001", 100000, "BEPMAY", date="2026-11-01"),
            row("T0002", 100000, "BEPMAY", date="2026-11-20"),
        ):
            empty, _ = ask(spend_plan(start="2026-11-05", end="2026-11-06"))
            none, _ = ask(spend_plan("theo_nhom", category="giai_tri", **NOVEMBER))
        self.assertIn("Không có khoản chi nào trong khoảng", empty["output"])
        self.assertIn(
            "Không có khoản chi nào được xếp vào nhóm Giải trí", none["output"]
        )

    def test_compare_marks_only_the_same_period_result_as_partial(self):
        out, _ = ask({"intent": "so_sanh", "m1": "2026-10", "m2": "2026-11"})
        flags = [r["partial"] for r in out["results"] if "partial" in r]
        self.assertEqual(flags, [True, False])
        out, _ = ask({"intent": "so_sanh", "m1": "2026-09", "m2": "2026-10"})
        self.assertEqual(
            [r["partial"] for r in out["results"] if "partial" in r], [False]
        )

    def test_compare_unchanged_and_category_absent(self):
        with statement(
            row("T0001", 100000, "BEPMAY", date="2026-09-10"),
            row("T0002", 100000, "BEPMAY", date="2026-10-10"),
        ):
            same, _ = ask({"intent": "so_sanh", "m1": "2026-09", "m2": "2026-10"})
            absent, _ = ask(
                {
                    "intent": "so_sanh",
                    "m1": "2026-09",
                    "m2": "2026-10",
                    "category": "giai_tri",
                }
            )
        self.assertIn("→ không đổi.", same["output"])
        self.assertIn(
            "cả hai tháng không có khoản chi nào ở nhóm Giải trí", absent["output"]
        )


if __name__ == "__main__":
    unittest.main()
