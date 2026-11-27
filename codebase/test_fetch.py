"""Test evidence/fetch_reviews.py bằng phản hồi GIẢ dựng trong test. Không gọi mạng, không ghi vào evidence/.

    python -m unittest discover -s codebase -p "test_*.py"
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "evidence"))

import fetch_reviews as fr  # noqa: E402


def entry(i, content="Ứng dụng dùng được", author="NGƯỜI VIẾT GIẢ"):
    return {"id": {"label": str(i)}, "updated": {"label": "2026-11-20T10:00:00-07:00"}, "im:rating": {"label": "3"},
            "title": {"label": "tiêu đề"}, "content": {"label": content},
            "author": {"name": {"label": author}, "uri": {"label": "https://example/author"}}}


class TestFetch(unittest.TestCase):
    def test_author_is_never_read(self):
        items = fr.parse_entries({"feed": {"entry": [{"id": {"label": "app"}}, entry(1)]}})
        self.assertEqual(len(items), 1)
        self.assertNotIn("NGƯỜI VIẾT", json.dumps(items, ensure_ascii=False))
        self.assertEqual(len(fr.parse_entries({"feed": {"entry": entry(2)}})), 1)

    def test_selection_rules(self):
        items = fr.parse_entries({"feed": {"entry": [
            entry(1), entry(1), entry(2, "👍👍"), entry(3, "Great app, works well"),
            entry(4, "app khong dang nhap duoc"), entry(5)]}})
        for item in items:
            if item["id"] == "3":
                item["title"] = "Nice"
        chosen, stats = fr.select([(1, items)])
        self.assertEqual([c["id"] for c in chosen], ["1", "4", "5"])
        self.assertEqual((stats["duplicate"], stats["no_text"], stats["not_vietnamese"]), (1, 1, 1))
        self.assertEqual(len(fr.select([(1, items)], limit=2)[0]), 2)

    def test_quote_is_two_verbatim_sentences_from_first_keyword(self):
        text = "Chào. Mình thất vọng. Lịch sử giao dịch khó xem! Tìm mãi không ra. Hết."
        self.assertEqual(fr.quote(text), "Lịch sử giao dịch khó xem! Tìm mãi không ra.")
        self.assertEqual(fr.quote("Câu một. Câu hai. Câu ba."), "Câu một. Câu hai.")
        self.assertTrue(len(fr.quote("rất dài " * 200)) <= fr.QUOTE_LIMIT + 2)

    def test_mask_hides_numbers_and_mail_but_keeps_money(self):
        out = fr.mask("gọi 0912 345 678, stk 19034567890012, mail a.b@x.com, mất 1.500.000 và 20.000.000đ")
        for secret in ("0912", "19034567890012", "a.b@x.com"):
            self.assertNotIn(secret, out)
        self.assertIn("1.500.000", out)
        self.assertIn("20.000.000", out)


if __name__ == "__main__":
    unittest.main()
