"""Test evidence/count.py bằng dữ liệu GIẢ trong thư mục tạm. Đây không phải bằng chứng và không ghi vào evidence/.

python -m unittest discover -s codebase -p "test_*.py"
"""

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "evidence"))

import count  # noqa: E402 — chỉ import được sau khi thêm evidence/ vào sys.path.

HEADER = ",".join(count.COLUMNS)
GOOD_ROW = "R1,app,kho,http://x,27/11,26/11,3,chu,kho_hieu_gd,TV,true"


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
        with open(
            os.path.join(ROOT, "evidence", "interviews", "TEMPLATE.md"),
            encoding="utf-8",
        ) as f:
            text = f.read()
        text = text.replace(
            "# P_ · [vai, vd: học viên L3 đi làm / lab coach]",
            "# %s · vai thử nghiệm" % code,
        )
        text = text.replace("- Gặp pain: __", "- Gặp pain: %s" % pain).replace(
            '- "…"', '- "DỮ LIỆU GIẢ %s"' % code
        )
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
        rows = [
            "R%02d,app,kho,http://x,27/11,26/11,3,chu,%s,TV,false" % (i, label)
            for i, label in enumerate(
                ["kho_hieu_gd", "kho_tong_hop", "ngan_sach", "khac"], start=1
            )
        ]
        path = self.write("reviews.csv", HEADER + "\n" + "\n".join(rows) + "\n")
        second = self.write("check.csv", "ma,nhan\nR01,kho_hieu_gd\nR02,khac\n")
        result = count.count_reviews(path, second)
        self.assertEqual((result["main"], result["n"], result["agree"]), (2, 4, (1, 2)))
        self.assertIn(
            "2/4 review (50%)", count.report(result, count.count_interviews(self.tmp))
        )
        self.assertIn(
            "Chưa đủ cỡ mẫu", count.report(result, count.count_interviews(self.tmp))
        )
        self.assertIn(
            "NHÁP, CHƯA PHẢI BẰNG CHỨNG",
            count.report(result, count.count_interviews(self.tmp)),
        )
        path = self.write(
            "reviews.csv",
            HEADER
            + "\n"
            + "\n".join(r.replace(",false", ",true") for r in rows)
            + "\n",
        )
        result = count.count_reviews(path)
        self.assertEqual((result["verified"], result["main_verified"]), (4, 2))
        self.assertNotIn("NHÁP", count.report(result, count.count_interviews(self.tmp)))

    def test_unlabelled_or_personal_rows_are_reported(self):
        path = self.write(
            "reviews.csv",
            HEADER + "\nR1,a,k,http://x,27/11,,1,goi 0912 345 678,,TV,false\n",
        )
        result = count.count_reviews(path)
        joined = " ".join(result["problems"])
        self.assertIn("chưa gắn nhãn", joined)
        self.assertIn("số điện thoại", joined)
        self.assertNotIn("%)", count.report(result, count.count_interviews(self.tmp)))

    def test_interview_thresholds(self):
        for pains, word in (
            (["co", "co"], "chưa đủ người"),
            (["co", "co", "không", "có"], "ĐẠT"),
            (["co", "khong", "mot phan"], "giả thuyết SAI"),
            (["co", "co", "khong"], "chưa đạt"),
        ):
            for name in os.listdir(self.tmp):
                os.remove(os.path.join(self.tmp, name))
            for i, pain in enumerate(pains, start=1):
                self.person("P%d" % i, pain)
            result = count.count_interviews(self.tmp)
            self.assertIn(word, result["verdict"], pains)
            self.assertEqual(result["people"][0]["quotes"], ["DỮ LIỆU GIẢ P1"])

    def test_unfilled_template_is_not_counted_as_pain(self):
        shutil.copy(
            os.path.join(ROOT, "evidence", "interviews", "TEMPLATE.md"),
            os.path.join(self.tmp, "P1.md"),
        )
        result = count.count_interviews(self.tmp)
        self.assertEqual(
            (result["n"], result["x"], result["people"][0]["quotes"]), (1, 0, [])
        )
        self.assertTrue(result["problems"])


class TestCountErrors(unittest.TestCase):
    """reviews.csv không đếm được: in dòng LỖI, không in x/N cho review, thoát 1."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.path = os.path.join(self.tmp, "reviews.csv")

    def put(self, data):
        with open(self.path, "wb") as f:
            f.write(data.encode("utf-8") if isinstance(data, str) else data)

    def run_main(self):
        screen = io.StringIO()
        with (
            mock.patch.object(count, "HERE", self.tmp),
            contextlib.redirect_stdout(screen),
        ):
            code = count.main()
        return code, screen.getvalue()

    def assert_error_state(self, *words):
        code, out = self.run_main()
        self.assertEqual(code, 1, out)
        section = out.split("## Review công khai", 1)[1]
        self.assertIn("- LỖI: ", section)
        self.assertIn("Không in x/N cho review", section)
        for word in words:
            self.assertIn(word, section)
        self.assertNotRegex(section, r"\d+/\d+ (review|dòng)")
        self.assertNotIn("| Nhãn |", section)
        self.assertNotIn("CHỜ DỮ LIỆU THẬT", section)

    def test_missing_reviews_file(self):
        self.assert_error_state("không thấy", "reviews.csv")

    def test_wrong_header(self):
        # dòng đủ nhãn, đủ cột: nếu đếm thì sẽ ra x/N. Tiêu đề lệch số cột thì dòng lệch được báo trước (nêu số dòng).
        for header, word in (
            ("ma,app,kho", "dòng 2"),
            (HEADER.replace("human_verified", "verified"), "phải có đúng các cột"),
            (HEADER + ",thua", "dòng 2"),
        ):
            with self.subTest(header=header):
                self.put(header + "\n" + GOOD_ROW + "\n")
                self.assert_error_state(word)

    def test_zero_byte_file(self):
        self.put("")
        self.assert_error_state("phải có đúng các cột")

    def test_directory_instead_of_file(self):
        os.mkdir(self.path)
        self.assert_error_state("không đọc được reviews.csv")

    def test_unreadable_file(self):
        self.put(HEADER + "\n" + GOOD_ROW + "\n")
        with mock.patch.object(
            count, "read_csv", side_effect=PermissionError("bị khoá")
        ):
            self.assert_error_state("không đọc được reviews.csv", "bị khoá")

    def test_undecodable_bytes(self):
        self.put(HEADER.encode("utf-8") + b"\nR1,a,k,\xff\xfe,x\n")
        self.assert_error_state("không đọc được reviews.csv", "utf-8")

    def test_field_over_csv_limit(self):
        self.put(HEADER + "\n" + "x" * 200000 + "\n")
        self.assert_error_state("không đọc được reviews.csv")

    def test_duplicate_code(self):
        # hai dòng đã gắn nhãn và đã kiểm: chỉ có mã trùng mới chặn được x/N
        for second in (GOOD_ROW, " " + GOOD_ROW.replace("kho_hieu_gd", "khac")):
            with self.subTest(second=second):
                self.put(HEADER + "\n" + GOOD_ROW + "\n" + second + "\n")
                self.assert_error_state("mã review trống hoặc trùng: 'R1'")
                result = count.count_reviews(self.path)
                self.assertEqual(result["errors"], ["mã review trống hoặc trùng: 'R1'"])

    def test_blank_code(self):
        self.put(HEADER + "\n" + GOOD_ROW.replace("R1,", ",", 1) + "\n")
        self.assert_error_state("mã review trống hoặc trùng: ''")

    def test_valid_file_exits_zero_with_counts(self):
        self.put(HEADER + "\n" + GOOD_ROW + "\n")
        code, out = self.run_main()
        self.assertEqual(code, 0, out)
        self.assertIn("1/1 review (100%)", out)
        self.assertNotIn("LỖI", out)
        self.assertEqual(count.count_reviews(self.path)["errors"], [])

    def test_header_only_file_exits_zero_as_waiting_for_data(self):
        self.put(HEADER + "\n")
        code, out = self.run_main()
        self.assertEqual(code, 0, out)
        self.assertIn("CHỜ DỮ LIỆU THẬT: evidence/reviews.csv", out)

    def test_script_exit_code(self):
        script = os.path.join(self.tmp, "count.py")
        shutil.copy(os.path.join(ROOT, "evidence", "count.py"), script)
        env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        for data, expected in ((None, 1), (HEADER + "\n" + GOOD_ROW + "\n", 0)):
            with self.subTest(expected=expected):
                if data is not None:
                    self.put(data)
                done = subprocess.run(
                    [sys.executable, script], capture_output=True, env=env, timeout=60
                )
                self.assertEqual(
                    done.returncode, expected, done.stderr.decode("utf-8", "replace")
                )

    def test_real_repo_data_exits_zero(self):
        screen = io.StringIO()
        with contextlib.redirect_stdout(screen):
            code = count.main()
        self.assertEqual(code, 0, screen.getvalue())
        self.assertNotIn("- LỖI", screen.getvalue())


class TestSecondLabelerAndInterviewErrors(unittest.TestCase):
    """CR2-06 và CR2-07: file đọc không được, hoặc sai tiêu đề, phải báo "- LỖI", thoát 1, không traceback."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.reviews = os.path.join(self.tmp, "reviews.csv")
        self.check = os.path.join(self.tmp, "reviews-check.csv")
        self.folder = os.path.join(self.tmp, "interviews")
        os.mkdir(self.folder)
        with open(self.reviews, "w", encoding="utf-8", newline="") as f:
            f.write(HEADER + "\n" + GOOD_ROW + "\n")

    def run_main(self):
        screen = io.StringIO()
        with (
            mock.patch.object(count, "HERE", self.tmp),
            contextlib.redirect_stdout(screen),
        ):
            code = count.main()
        return code, screen.getvalue()

    def put(self, path, data):
        with open(path, "wb") as f:
            f.write(data.encode("utf-8") if isinstance(data, str) else data)

    def test_unreadable_or_directory_second_labeler_file_is_an_error(self):
        for label, make in (
            (
                "không giải mã được",
                lambda: self.put(self.check, b"ma,nhan\nR1,\xff\xfe\n"),
            ),
            ("là thư mục", lambda: os.mkdir(self.check)),
        ):
            with self.subTest(label):
                make()
                code, out = self.run_main()
                self.assertEqual(code, 1, out)
                self.assertIn("- LỖI: không đọc được reviews-check.csv", out)
                self.assertNotIn("Traceback", out)
                self.assertNotIn("khớp", out)
                self.assertNotIn("CHỜ DỮ LIỆU THẬT: evidence/reviews-check.csv", out)
                if os.path.isdir(self.check):
                    os.rmdir(self.check)
                else:
                    os.remove(self.check)

    def test_unreadable_or_directory_interview_file_is_an_error(self):
        for label, make in (
            (
                "không giải mã được",
                lambda: self.put(os.path.join(self.folder, "P1.md"), b"# P1\xff\xfe"),
            ),
            ("là thư mục", lambda: os.mkdir(os.path.join(self.folder, "P2.md"))),
        ):
            with self.subTest(label):
                make()
                code, out = self.run_main()
                self.assertEqual(code, 1, out)
                section = out.split("## Review công khai", 1)[0]
                self.assertIn("- LỖI: không đọc được P", section)
                self.assertIn("không kết luận", section)
                self.assertNotIn("Traceback", out)
                self.assertNotIn("CHỜ DỮ LIỆU THẬT: chưa có file", section)
                target = os.path.join(
                    self.folder, "P1.md" if label.startswith("không") else "P2.md"
                )
                if os.path.isdir(target):
                    os.rmdir(target)
                else:
                    os.remove(target)

    def test_check_file_without_ma_nhan_header_is_an_error_not_waiting(self):
        for data in ("foo,bar\nR1,kho_hieu_gd\n", "", "ma\nR1\n"):
            with self.subTest(data=data):
                self.put(self.check, data)
                code, out = self.run_main()
                self.assertEqual(code, 1, out)
                self.assertIn(
                    "- LỖI: reviews-check.csv phải có tiêu đề cột ma,nhan", out
                )
                self.assertNotIn("CHỜ DỮ LIỆU THẬT: evidence/reviews-check.csv", out)
                self.assertNotIn("khớp", out)

    def test_missing_check_file_still_waits_for_real_data(self):
        code, out = self.run_main()
        self.assertEqual(code, 0, out)
        self.assertIn("[CHỜ DỮ LIỆU THẬT: evidence/reviews-check.csv]", out)
        self.assertNotIn("- LỖI", out)


if __name__ == "__main__":
    unittest.main()
