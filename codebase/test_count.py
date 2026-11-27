"""Test evidence/count.py bằng dữ liệu GIẢ trong thư mục tạm. Đây không phải bằng chứng và không ghi vào evidence/.

    python -m unittest discover -s codebase -p "test_*.py"
"""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "evidence"))

import count  # noqa: E402

HEADER = ",".join(count.COLUMNS)


class TestCount(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def person(self, code, pain):
        with open(os.path.join(ROOT, "evidence", "interviews", "TEMPLATE.md"), encoding="utf-8") as f:
            text = f.read()
        text = text.replace("# P_ · [vai, vd: học viên L3 đi làm / lab coach]", "# %s · vai thử nghiệm" % code)
        text = text.replace("- Gặp pain: __", "- Gặp pain: %s" % pain).replace('- "…"', '- "DỮ LIỆU GIẢ %s"' % code)
        self.write(code + ".md", text)

    def test_real_folder_files_are_empty_or_valid(self):
        path = os.path.join(ROOT, "evidence", "reviews.csv")
        self.assertEqual(count.read_csv(path)[0], count.COLUMNS)

    def test_empty(self):
        reviews = count.count_reviews(self.write("reviews.csv", HEADER + "\n"))
        people = count.count_interviews(self.tmp)
        self.assertEqual((reviews["n"], people["n"]), (0, 0))
        self.assertIn("CHỜ DỮ LIỆU THẬT", count.report(reviews, people))

    def test_review_counts_denominator_is_all_rows(self):
        rows = ["R%02d,app,kho,http://x,27/11,26/11,3,chu,%s,TV,false" % (i, label) for i, label in
                enumerate(["kho_hieu_gd", "kho_tong_hop", "ngan_sach", "khac"], start=1)]
        path = self.write("reviews.csv", HEADER + "\n" + "\n".join(rows) + "\n")
        second = self.write("check.csv", "ma,nhan\nR01,kho_hieu_gd\nR02,khac\n")
        result = count.count_reviews(path, second)
        self.assertEqual((result["main"], result["n"], result["agree"]), (2, 4, (1, 2)))
        self.assertIn("2/4 review (50%)", count.report(result, count.count_interviews(self.tmp)))
        self.assertIn("Chưa đủ cỡ mẫu", count.report(result, count.count_interviews(self.tmp)))
        self.assertIn("NHÁP, CHƯA PHẢI BẰNG CHỨNG", count.report(result, count.count_interviews(self.tmp)))
        path = self.write("reviews.csv", HEADER + "\n" + "\n".join(r.replace(",false", ",true") for r in rows) + "\n")
        result = count.count_reviews(path)
        self.assertEqual((result["verified"], result["main_verified"]), (4, 2))
        self.assertNotIn("NHÁP", count.report(result, count.count_interviews(self.tmp)))

    def test_unlabelled_or_personal_rows_are_reported(self):
        path = self.write("reviews.csv", HEADER + "\nR1,a,k,http://x,27/11,,1,goi 0912 345 678,,TV,false\n")
        result = count.count_reviews(path)
        joined = " ".join(result["problems"])
        self.assertIn("chưa gắn nhãn", joined)
        self.assertIn("số điện thoại", joined)
        self.assertNotIn("%)", count.report(result, count.count_interviews(self.tmp)))

    def test_interview_thresholds(self):
        for pains, word in ((["co", "co"], "chưa đủ người"), (["co", "co", "không", "có"], "ĐẠT"),
                            (["co", "khong", "mot phan"], "giả thuyết SAI"), (["co", "co", "khong"], "chưa đạt")):
            for name in os.listdir(self.tmp):
                os.remove(os.path.join(self.tmp, name))
            for i, pain in enumerate(pains, start=1):
                self.person("P%d" % i, pain)
            result = count.count_interviews(self.tmp)
            self.assertIn(word, result["verdict"], pains)
            self.assertEqual(result["people"][0]["quotes"], ["DỮ LIỆU GIẢ P1"])

    def test_unfilled_template_is_not_counted_as_pain(self):
        shutil.copy(os.path.join(ROOT, "evidence", "interviews", "TEMPLATE.md"), os.path.join(self.tmp, "P1.md"))
        result = count.count_interviews(self.tmp)
        self.assertEqual((result["n"], result["x"], result["people"][0]["quotes"]), (1, 0, []))
        self.assertTrue(result["problems"])


if __name__ == "__main__":
    unittest.main()
