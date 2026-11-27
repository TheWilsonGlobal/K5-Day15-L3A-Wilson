"""Test evidence/fetch_reviews.py bằng phản hồi GIẢ dựng trong test. Không gọi mạng, không ghi vào evidence/.

python -m unittest discover -s codebase -p "test_*.py"
"""

import contextlib
import csv
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "evidence"))

import count  # noqa: E402 — chỉ import được sau khi thêm evidence/ vào sys.path.
import fetch_reviews as fr  # noqa: E402 — chỉ import được sau khi thêm evidence/ vào sys.path.

APP_NAMES = [name for name, _ in fr.APPS]
LOG_SENTINEL = b'{"sentinel": true}\n'
REAL_FETCH_PAGE = (
    fr.fetch_page
)  # bản thật, lấy trước mọi mock.patch; TestFeedShape dùng lại nó


def entry(i, content="Ứng dụng dùng được", author="NGƯỜI VIẾT GIẢ"):
    return {
        "id": {"label": str(i)},
        "updated": {"label": "2026-11-20T10:00:00-07:00"},
        "im:rating": {"label": "3"},
        "title": {"label": "tiêu đề"},
        "content": {"label": content},
        "author": {
            "name": {"label": author},
            "uri": {"label": "https://example/author"},
        },
    }


def review(code, content="Ứng dụng dùng được"):
    return {
        "id": str(code),
        "date": "2026-11-20",
        "rating": "3",
        "title": "t",
        "content": content,
    }


def row(**values):
    out = dict.fromkeys(count.COLUMNS, "")
    out.update(values)
    return out


def csv_of(rows, columns=None):
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=columns or count.COLUMNS, extrasaction="ignore"
    )
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


# Mã trong mẫu giả: app thứ i (0..2), trang p (1..2), dòng k (0..24) → i*1000 + p*100 + k.
OLD_ROWS = [
    # đã kiểm, có trong mẫu mới (human_verified có dấu cách ở cuối)
    row(
        ma="100",
        app="MoMo",
        nhan="kho_hieu_gd",
        human_verified="true ",
        trich="trích A",
        nguoi_gan="Ng A",
        link="http://cu/a",
        ngay_xem="01/11",
    ),
    # đã kiểm, không còn trong mẫu mới
    row(ma="999", app="MoMo", nhan="khac", human_verified="TRUE", trich="trích B"),
    # đã kiểm, thuộc app sẽ bị lỗi
    row(
        ma="1100",
        app="Techcombank Mobile",
        nhan="ngan_sach",
        human_verified=" true",
        trich="trích C",
    ),
    # nháp chưa kiểm, không còn trong mẫu mới
    row(ma="5", app="MoMo", nhan="khac", human_verified="false", trich="nháp D"),
    # nháp chưa kiểm của app sẽ bị lỗi, mã vẫn có trong phản hồi giả
    row(
        ma="1101",
        app="Techcombank Mobile",
        nhan="khac",
        human_verified="false",
        trich="nháp E",
    ),
]
VERIFIED = [OLD_ROWS[0], OLD_ROWS[1], OLD_ROWS[2]]


class Base(unittest.TestCase):
    """Mọi đường dẫn trỏ vào thư mục tạm; mạng bị thay bằng trang giả."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.reviews = os.path.join(self.tmp, "reviews.csv")
        self.log = os.path.join(self.tmp, "fetch-log.json")
        self.calls = []
        self.broken = {}  # chỉ số app → (trang đầu tiên lỗi, "raise" | "empty")
        self.content = "Ứng dụng dùng được"
        self.start(mock.patch.object(fr, "REVIEWS", self.reviews))
        self.start(mock.patch.object(fr, "LOG", self.log))
        self.start(mock.patch.object(fr, "fetch_page", side_effect=self.page))
        self.sleep = self.start(mock.patch.object(fr.time, "sleep"))
        self.start(
            mock.patch.object(
                fr.urllib.request,
                "urlopen",
                side_effect=AssertionError("test không được gọi mạng"),
            )
        )

    def start(self, patcher):
        self.addCleanup(patcher.stop)
        return patcher.start()

    def page(self, app_id, number):
        self.calls.append((app_id, number))
        index = [a for _, a in fr.APPS].index(app_id)
        first_bad, kind = self.broken.get(index, (None, None))
        if first_bad is not None and number >= first_bad:
            if kind == "empty":
                return []
            raise OSError("lỗi giả lập app %d" % index)
        if number > 2:
            return []
        return [
            review(index * 1000 + number * 100 + k, self.content) for k in range(25)
        ]

    def main(self, *args):
        screen = io.StringIO()
        with contextlib.redirect_stdout(screen), contextlib.redirect_stderr(screen):
            code = fr.main(list(args))
        return code, screen.getvalue()

    def put(self, path, data):
        if isinstance(data, str):
            data = data.encode("utf-8")
        with open(path, "wb") as f:
            f.write(data)
        return path

    def seed(self, rows=OLD_ROWS):
        """reviews.csv và fetch-log.json cũ. → hai chuỗi byte để so sánh."""
        self.put(self.reviews, csv_of(rows).encode("utf-8-sig"))
        self.put(self.log, LOG_SENTINEL)
        return self.snapshot()

    def snapshot(self):
        out = []
        for path in (self.reviews, self.log):
            if os.path.isfile(path):
                with open(path, "rb") as f:
                    out.append(f.read())
            else:
                out.append(None)
        return tuple(out)

    def rows(self):
        with open(self.reviews, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def log_data(self):
        with open(self.log, encoding="utf-8") as f:
            return json.load(f)

    def assert_clean_error(self, code, out, *words):
        self.assertEqual(code, 1, out)
        self.assertIn("LỖI", out)
        self.assertNotIn("Traceback", out)
        for word in words:
            self.assertIn(word, out)


class TestFetch(unittest.TestCase):
    def test_author_is_never_read(self):
        items = fr.parse_entries(
            {"feed": {"entry": [{"id": {"label": "app"}}, entry(1)]}}
        )
        self.assertEqual(len(items), 1)
        self.assertNotIn("NGƯỜI VIẾT", json.dumps(items, ensure_ascii=False))
        self.assertEqual(len(fr.parse_entries({"feed": {"entry": entry(2)}})), 1)

    def test_selection_rules(self):
        items = fr.parse_entries(
            {
                "feed": {
                    "entry": [
                        entry(1),
                        entry(1),
                        entry(2, "👍👍"),
                        entry(3, "Great app, works well"),
                        entry(4, "app khong dang nhap duoc"),
                        entry(5),
                    ]
                }
            }
        )
        for item in items:
            if item["id"] == "3":
                item["title"] = "Nice"
        chosen, stats = fr.select([(1, items)])
        self.assertEqual([c["id"] for c in chosen], ["1", "4", "5"])
        self.assertEqual(
            (stats["duplicate"], stats["no_text"], stats["not_vietnamese"]), (1, 1, 1)
        )
        self.assertEqual(len(fr.select([(1, items)], limit=2)[0]), 2)

    def test_quote_is_two_verbatim_sentences_from_first_keyword(self):
        text = "Chào. Mình thất vọng. Lịch sử giao dịch khó xem! Tìm mãi không ra. Hết."
        self.assertEqual(fr.quote(text), "Lịch sử giao dịch khó xem! Tìm mãi không ra.")
        self.assertEqual(fr.quote("Câu một. Câu hai. Câu ba."), "Câu một. Câu hai.")
        self.assertTrue(len(fr.quote("rất dài " * 200)) <= fr.QUOTE_LIMIT + 2)

    def test_mask_hides_numbers_and_mail_but_keeps_money(self):
        out = fr.mask(
            "gọi 0912 345 678, stk 19034567890012, mail a.b@x.com, mất 1.500.000 và 20.000.000đ"
        )
        for secret in ("0912", "19034567890012", "a.b@x.com"):
            self.assertNotIn(secret, out)
        self.assertIn("1.500.000", out)
        self.assertIn("20.000.000", out)


class TestFetchPage(unittest.TestCase):
    """fetch_page thật, chỉ urlopen bị thay."""

    def open_with(self, **kwargs):
        patcher = mock.patch.object(fr.urllib.request, "urlopen", **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def test_requests_the_public_feed_and_parses_it(self):
        body = json.dumps({"feed": {"entry": [entry(7)]}}).encode("utf-8")
        urlopen = self.open_with(return_value=io.BytesIO(body))
        items = fr.fetch_page(123, 4)
        self.assertEqual([i["id"] for i in items], ["7"])
        self.assertNotIn("NGƯỜI VIẾT", json.dumps(items, ensure_ascii=False))
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, fr.URL % (4, 123))
        self.assertEqual(request.get_header("User-agent"), fr.USER_AGENT)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 60)

    def test_feed_without_entries_is_empty(self):
        self.open_with(return_value=io.BytesIO(b'{"feed": {}}'))
        self.assertEqual(fr.fetch_page(1, 1), [])

    def test_errors_are_raised_not_turned_into_an_empty_page(self):
        for kwargs, error in (
            ({"side_effect": urllib.error.URLError("mất mạng")}, urllib.error.URLError),
            ({"return_value": io.BytesIO(b"<html>")}, json.JSONDecodeError),
            ({"return_value": io.BytesIO(b"\xff\xfe")}, UnicodeDecodeError),
        ):
            with self.subTest(error=error.__name__):
                with (
                    mock.patch.object(fr.urllib.request, "urlopen", **kwargs),
                    self.assertRaises(error),
                ):
                    fr.fetch_page(1, 1)


class TestPagesOf(unittest.TestCase):
    def walk(self, side_effect):
        errors = []
        with (
            mock.patch.object(fr, "fetch_page", side_effect=side_effect) as fetch_page,
            mock.patch.object(fr.time, "sleep") as sleep,
        ):
            pages = list(fr.pages_of(1, errors))
        return pages, errors, fetch_page, sleep

    def test_exception_is_recorded_with_page_and_type_then_stops(self):
        pages, errors, fetch_page, _ = self.walk(
            [[review(1)], ValueError("x" * 500), [review(2)]]
        )
        self.assertEqual([p for p, _ in pages], [1])
        self.assertEqual(errors, ["trang 2: ValueError: " + "x" * 200])
        self.assertEqual(fetch_page.call_count, 2)

    def test_empty_page_is_recorded_then_stops(self):
        pages, errors, fetch_page, _ = self.walk([[], [review(1)]])
        self.assertEqual((pages, errors), ([], ["trang 1: không trả review nào"]))
        self.assertEqual(fetch_page.call_count, 1)

    def test_stops_at_max_page_and_pauses_between_pages(self):
        pages, errors, fetch_page, sleep = self.walk(
            lambda app_id, page: [review(page)]
        )
        self.assertEqual([p for p, _ in pages], list(range(1, fr.MAX_PAGE + 1)))
        self.assertEqual(
            (errors, fetch_page.call_count, sleep.call_count),
            ([], fr.MAX_PAGE, fr.MAX_PAGE),
        )


class TestFetchFailLoud(Base):
    """E11: app lỗi thì lệnh phải nói lỗi, không ghi mẫu thiếu mà thoát 0."""

    def test_all_apps_ok_writes_reviews_and_log(self):
        code, out = self.main()
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.rows()), 150)
        self.assertNotIn("CẢNH BÁO", out)
        log = self.log_data()
        self.assertEqual(
            (log["failed_apps"], log["partial"], log["allow_partial"]),
            ([], False, False),
        )
        self.assertEqual([a["app"] for a in log["apps"]], APP_NAMES)
        first = self.rows()[0]
        self.assertEqual(
            (first["ma"], first["app"], first["human_verified"], first["nhan"]),
            ("100", "MoMo", "false", ""),
        )
        self.assertEqual(first["link"], fr.URL % (1, fr.APPS[0][1]))

    def test_all_apps_fail_prints_each_error_and_writes_nothing(self):
        for flags in (
            (),
            ("--refresh",),
            ("--refresh", "--allow-partial"),
            ("--allow-partial",),
        ):
            with self.subTest(flags=flags):
                self.broken = {i: (1, "raise") for i in range(3)}
                code, out = self.main(*flags)
                self.assert_clean_error(
                    code, out, "mọi app đều lỗi. Không ghi file nào."
                )
                for i, name in enumerate(APP_NAMES):
                    self.assertIn(
                        "LỖI %s: trang 1: OSError: lỗi giả lập app %d" % (name, i), out
                    )
                self.assertEqual(os.listdir(self.tmp), [])

    def test_all_apps_fail_leaves_existing_files_byte_identical(self):
        before = self.seed()
        self.broken = {i: (2, "raise") for i in range(3)}
        for flags in (("--refresh",), ("--refresh", "--allow-partial")):
            with self.subTest(flags=flags):
                code, out = self.main(*flags)
                self.assert_clean_error(
                    code, out, "mọi app đều lỗi. Không ghi file nào."
                )
                self.assertEqual(self.snapshot(), before)

    def test_one_app_fails_without_allow_partial_changes_nothing(self):
        before = self.seed()
        for index, name in enumerate(APP_NAMES):
            # trang 2 rỗng là hết feed (PM 27/11), không phải lỗi: xem test_empty_page_after_the_first_is_end_of_feed
            for page, kind in ((1, "raise"), (2, "raise"), (1, "empty")):
                with self.subTest(app=name, page=page, kind=kind):
                    self.broken = {index: (page, kind)}
                    code, out = self.main("--refresh")
                    self.assert_clean_error(
                        code, out, "CẢNH BÁO: app lỗi: %s." % name, "--allow-partial"
                    )
                    self.assertEqual(self.snapshot(), before)
                    self.assertEqual(
                        sorted(os.listdir(self.tmp)), ["fetch-log.json", "reviews.csv"]
                    )

    def test_one_app_fails_on_first_run_creates_no_file_and_no_dump(self):
        self.broken = {2: (1, "raise")}
        dump = os.path.join(self.tmp, "dump.txt")
        code, out = self.main("--dump", dump)
        self.assert_clean_error(code, out, "CẢNH BÁO: app lỗi: Money Lover.")
        self.assertEqual(os.listdir(self.tmp), [])

    def test_two_failed_apps_are_both_named(self):
        self.broken = {0: (1, "raise"), 2: (1, "empty")}
        code, out = self.main()
        self.assert_clean_error(code, out, "CẢNH BÁO: app lỗi: MoMo, Money Lover.")
        self.assertEqual(os.listdir(self.tmp), [])

    def test_allow_partial_writes_partial_sample_and_says_so(self):
        for page in (1, 2):
            with self.subTest(failing_page=page):
                self.seed()
                self.broken = {1: (page, "raise")}
                code, out = self.main("--refresh", "--allow-partial")
                self.assertEqual(code, 0, out)
                self.assertIn("CẢNH BÁO: app lỗi: Techcombank Mobile.", out)
                self.assertIn("--allow-partial: ghi mẫu TỪNG PHẦN", out)
                self.assertIn("THIẾU app: Techcombank Mobile", out)
                rows = self.rows()
                # app lỗi không đóng góp mẫu mới (kể cả trang đã tải được); chỉ còn dòng đã kiểm
                self.assertEqual(
                    [r["ma"] for r in rows if r["app"] == "Techcombank Mobile"],
                    ["1100"],
                )
                self.assertEqual(sum(r["app"] == "Money Lover" for r in rows), 50)
                log = self.log_data()
                self.assertEqual(log["failed_apps"], ["Techcombank Mobile"])
                self.assertIs(log["partial"], True)
                self.assertIs(log["allow_partial"], True)
                errors = {a["app"]: a["errors"] for a in log["apps"]}
                self.assertEqual(
                    errors["Techcombank Mobile"],
                    ["trang %d: OSError: lỗi giả lập app 1" % page],
                )
                self.assertEqual(errors["MoMo"], [])

    def test_allow_partial_with_no_failure_is_not_marked_partial(self):
        code, out = self.main("--allow-partial")
        self.assertEqual(code, 0, out)
        self.assertNotIn("CẢNH BÁO", out)
        log = self.log_data()
        self.assertEqual(
            (log["failed_apps"], log["partial"], log["allow_partial"]),
            ([], False, True),
        )

    def test_allow_partial_without_refresh_is_refused_when_rows_exist(self):
        before = self.seed()
        self.broken = {1: (1, "raise")}
        code, out = self.main("--allow-partial")
        self.assert_clean_error(code, out, "--refresh")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.calls, [])

    def test_empty_page_after_the_first_is_end_of_feed_but_empty_first_page_is_a_failure(
        self,
    ):
        # CR2-08 (PM 27/11): MoMo có 25 review ở trang 1, trang 2 rỗng → hết feed, thành công với 25 dòng
        self.broken = {0: (2, "empty")}
        code, out = self.main()
        self.assertEqual(code, 0, out)
        self.assertNotIn("CẢNH BÁO", out)
        self.assertEqual(sum(r["app"] == "MoMo" for r in self.rows()), 25)
        log = self.log_data()
        momo = log["apps"][0]
        self.assertEqual(
            (momo["app"], momo["kept"], momo["pages"], momo["errors"]),
            ("MoMo", 25, 1, []),
        )
        self.assertEqual(log["failed_apps"], [])
        # trang 1 rỗng vẫn là lỗi của app, dù các trang khác ổn
        self.broken = {0: (1, "empty")}
        code, out = self.main("--refresh")
        self.assert_clean_error(
            code, out, "CẢNH BÁO: app lỗi: MoMo.", "trang 1: không trả review nào"
        )

    def test_no_review_kept_writes_nothing(self):
        self.content = "👍👍"
        self.broken = {}
        with mock.patch.object(fr, "MAX_PAGE", 2):
            code, out = self.main()
        self.assert_clean_error(code, out, "Không lấy được review nào")
        self.assertEqual(os.listdir(self.tmp), [])


class TestFetchKeepsHumanWork(Base):
    def test_existing_rows_are_not_overwritten_without_refresh(self):
        # cả dòng nháp lẫn dòng đã kiểm đều chặn việc ghi đè
        for rows in (OLD_ROWS, [OLD_ROWS[3]]):
            with self.subTest(rows=len(rows)):
                before = self.seed(rows)
                code, out = self.main()
                self.assert_clean_error(
                    code, out, "reviews.csv đã có %d dòng" % len(rows), "--refresh"
                )
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.calls, [])

    def test_header_only_file_needs_no_refresh(self):
        self.seed([])
        code, out = self.main()
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.rows()), 150)

    def assert_verified_kept(self, rows):
        for old in VERIFIED:
            self.assertEqual([r for r in rows if r["ma"] == old["ma"]], [old])

    def test_refresh_keeps_every_verified_row_verbatim(self):
        self.seed()
        code, out = self.main("--refresh")
        self.assertEqual(code, 0, out)
        rows = self.rows()
        self.assert_verified_kept(rows)
        codes = [r["ma"] for r in rows]
        self.assertNotIn("5", codes)  # nháp không còn trong mẫu thì bỏ như trước
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(len(rows), 151)  # 150 mẫu mới (gồm 100 và 1100) + 999
        fresh = [r for r in rows if r["ma"] == "1101"][0]
        self.assertEqual((fresh["nhan"], fresh["human_verified"]), ("", "false"))

    def test_refresh_keeps_verified_rows_of_a_failed_app(self):
        self.seed()
        self.broken = {1: (1, "raise")}
        code, out = self.main("--refresh", "--allow-partial")
        self.assertEqual(code, 0, out)
        rows = self.rows()
        self.assert_verified_kept(rows)
        codes = [r["ma"] for r in rows]
        self.assertNotIn("5", codes)
        self.assertNotIn("1101", codes)
        self.assertEqual(len(rows), 102)

    def test_refresh_keeps_verified_rows_when_new_sample_is_empty(self):
        self.seed()
        self.content = "👍👍"
        with mock.patch.object(fr, "MAX_PAGE", 2):
            code, out = self.main("--refresh")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.rows(), VERIFIED)

    def test_refresh_keeps_both_rows_when_a_verified_code_is_duplicated(self):
        twins = [
            row(ma="100", app="MoMo", nhan="khac", human_verified="true", trich="một"),
            row(
                ma="100",
                app="MoMo",
                nhan="kho_tim_gd",
                human_verified="true",
                trich="hai",
            ),
        ]
        self.seed(twins)
        code, out = self.main("--refresh")
        self.assertEqual(code, 0, out)
        self.assertEqual([r for r in self.rows() if r["ma"] == "100"], twins)

    def test_refresh_refuses_a_reviews_file_it_cannot_trust(self):
        header = ",".join(count.COLUMNS)
        wrong = csv_of(OLD_ROWS).replace("human_verified", "verified", 1)
        for label, data in (
            ("sai cột", wrong.encode("utf-8-sig")),
            ("không giải mã được", header.encode() + b"\n\xff\xfe\n"),
            ("trường quá dài", (header + "\n" + "x" * 200000 + "\n").encode()),
        ):
            with self.subTest(label):
                self.put(self.reviews, data)
                code, out = self.main("--refresh")
                self.assert_clean_error(code, out, "reviews.csv")
                with open(self.reviews, "rb") as f:
                    self.assertEqual(f.read(), data)
                self.assertFalse(os.path.exists(self.log))
                self.assertEqual(self.calls, [])

    def test_refresh_refuses_a_reviews_path_that_is_a_directory(self):
        os.mkdir(self.reviews)
        code, out = self.main("--refresh")
        self.assert_clean_error(code, out, "không đọc được reviews.csv")
        self.assertEqual(self.calls, [])

    def test_replace_failure_is_a_clean_error_and_keeps_the_old_files(self):
        before = self.seed()
        with mock.patch.object(
            fr.os, "replace", side_effect=PermissionError("đang mở")
        ):
            code, out = self.main("--refresh")
        self.assert_clean_error(code, out, "không ghi được", "đang mở")
        self.assertEqual(self.snapshot(), before)

    def test_log_write_failure_exits_non_zero(self):
        self.log = os.path.join(self.tmp, "khong-co", "fetch-log.json")
        with mock.patch.object(fr, "LOG", self.log):
            code, out = self.main()
        self.assert_clean_error(code, out, "không ghi được", "fetch-log.json")


class TestRaggedReviews(Base):
    """CR2-05: dòng reviews.csv thừa hoặc thiếu ô so với tiêu đề → dừng, nêu số dòng, không ghi gì."""

    def bad_file(self, bad_line):
        header = ",".join(count.COLUMNS)
        good = csv_of([OLD_ROWS[0]]).splitlines()[1]
        data = header + "\r\n" + good + "\r\n" + bad_line(good) + "\r\n"
        self.put(self.reviews, data.encode("utf-8-sig"))
        self.put(self.log, LOG_SENTINEL)
        return self.snapshot()

    def test_extra_or_missing_cells_stop_refresh_and_apply_labels(self):
        drafts = os.path.join(self.tmp, "draft.csv")
        self.put(drafts, "ma,nhan,che\n1,khac,\n")
        for label, bad_line in (
            ("thừa ô", lambda good: good + ",thua"),
            ("thiếu ô", lambda good: good.rsplit(",", 1)[0]),
        ):
            for flags in (("--refresh",), ("--apply-labels", drafts)):
                with self.subTest(case=label, flags=flags[0]):
                    before = self.bad_file(bad_line)
                    code, out = self.main(*flags)
                    self.assert_clean_error(code, out, "reviews.csv", "dòng 3")
                    self.assertEqual(self.snapshot(), before)
                    self.assertEqual(self.calls, [])
                    self.assertEqual(
                        sorted(os.listdir(self.tmp)),
                        sorted(["reviews.csv", "fetch-log.json", "draft.csv"]),
                    )


class TestAtomicWrites(Base):
    """CR2-09 và CR2-10: file tạm không còn sót; mọi file tạm ghi xong trước khi đổi tên file đích."""

    def test_failed_replace_leaves_no_temp_file(self):
        before = self.seed()
        with mock.patch.object(
            fr.os, "replace", side_effect=PermissionError("đang mở")
        ):
            code, out = self.main("--refresh")
        self.assert_clean_error(code, out, "không ghi được", "đang mở")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(
            sorted(os.listdir(self.tmp)), ["fetch-log.json", "reviews.csv"]
        )

    def test_failed_temp_write_changes_no_target(self):
        before = self.seed()
        self.log = os.path.join(self.tmp, "khong-co", "fetch-log.json")
        with mock.patch.object(fr, "LOG", self.log):
            code, out = self.main("--refresh")
        self.assert_clean_error(code, out, "không ghi được", "fetch-log.json")
        self.assertEqual(self.snapshot()[0], before[0])
        self.assertEqual(
            sorted(os.listdir(self.tmp)), ["fetch-log.json", "reviews.csv"]
        )

    def test_replace_midway_names_the_files_that_changed(self):
        before = self.seed()
        real_replace = os.replace
        calls = []

        def second_fails(src, dst):
            calls.append(dst)
            if len(calls) == 2:
                raise PermissionError("đang mở")
            return real_replace(src, dst)

        with mock.patch.object(fr.os, "replace", side_effect=second_fails):
            code, out = self.main("--refresh")
        self.assert_clean_error(
            code, out, "không ghi được", "fetch-log.json", "Đã đổi:", "Chưa đổi:"
        )
        self.assertIn("Chưa đổi: %s" % self.log, out)
        self.assertNotEqual(self.snapshot()[0], before[0])
        self.assertEqual(self.snapshot()[1], before[1])
        self.assertEqual(
            sorted(os.listdir(self.tmp)), ["fetch-log.json", "reviews.csv"]
        )

    def test_lone_surrogate_in_review_removes_every_temp_file(self):
        # CR3-06: UnicodeEncodeError không phải OSError. File tạm đã mở phải bị xoá, đích không đổi, không traceback.
        before = self.seed()
        self.content = "Ứng dụng dùng được \ud800"
        dump = os.path.join(self.tmp, "dump.txt")
        code, out = self.main("--refresh", "--dump", dump)
        self.assert_clean_error(code, out, "không ghi được", "Không file nào bị đổi")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(
            sorted(os.listdir(self.tmp)), ["fetch-log.json", "reviews.csv"]
        )
        self.assertFalse(os.path.exists(dump))


class TestFeedShape(Base):
    """CR3-09: fetch_page thật, chỉ urlopen bị thay. Thân không có object feed là lỗi của app ở mọi trang,
    kể cả trang 2. Chỉ object feed không có entry mới là hết feed."""

    def run_with(self, overrides, *args):
        """Mọi app: trang 1 có 25 review, trang sau là {"feed": {}}. overrides: {(app_id, trang): thân}."""

        def fake(request, timeout):
            match = re.search(r"page=(\d+)/id=(\d+)", request.full_url)
            number, app_id = int(match.group(1)), int(match.group(2))
            if (app_id, number) in overrides:
                body = overrides[(app_id, number)]
            elif number == 1:
                body = {
                    "feed": {"entry": [entry("%d-%d" % (app_id, k)) for k in range(25)]}
                }
            else:
                body = {"feed": {}}
            return io.BytesIO(
                body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
            )

        with (
            mock.patch.object(fr, "fetch_page", REAL_FETCH_PAGE),
            mock.patch.object(fr.urllib.request, "urlopen", side_effect=fake),
        ):
            return self.main(*args)

    def test_page_two_without_feed_object_is_an_app_error(self):
        for body in (b"{}", {"error": "rate limited"}):
            with self.subTest(body=body):
                code, out = self.run_with({(fr.APPS[0][1], 2): body})
                self.assert_clean_error(
                    code, out, "CẢNH BÁO: app lỗi: MoMo.", "MoMo", "trang 2", "'feed'"
                )
                self.assertEqual(os.listdir(self.tmp), [])

    def test_page_two_without_feed_object_with_allow_partial_is_recorded_for_its_app(
        self,
    ):
        code, out = self.run_with({(fr.APPS[0][1], 2): b"{}"}, "--allow-partial")
        self.assertEqual(code, 0, out)
        log = self.log_data()
        momo_log = log["apps"][0]
        self.assertEqual(
            (momo_log["app"], momo_log["kept"], momo_log["pages"]), ("MoMo", 25, 1)
        )
        self.assertEqual(len(momo_log["errors"]), 1)
        self.assertTrue(
            momo_log["errors"][0].startswith("trang 2: ValueError"), momo_log["errors"]
        )
        self.assertEqual(log["failed_apps"], ["MoMo"])

    def test_page_two_with_feed_but_no_entries_is_end_of_feed(self):
        code, out = self.run_with({(fr.APPS[0][1], 2): {"feed": {}}})
        self.assertEqual(code, 0, out)
        self.assertNotIn("CẢNH BÁO", out)
        self.assertEqual(sum(r["app"] == "MoMo" for r in self.rows()), 25)
        self.assertEqual(self.log_data()["apps"][0]["errors"], [])


class TestDump(Base):
    def setUp(self):
        super().setUp()
        # "repo" giả: nếu rào chắn hỏng thì file lọt vào thư mục tạm, không phải repo thật.
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.repo, "evidence"))
        self.start(mock.patch.object(fr, "ROOT", self.repo, create=True))

    def test_dump_inside_repo_is_refused_before_any_network_call(self):
        for path in (
            os.path.join(self.repo, "dump.txt"),
            os.path.join(self.repo, "evidence", "dump.txt"),
            os.path.join(self.repo, "evidence", "..", "..", "repo", "dump.txt"),
        ):
            with self.subTest(path=path):
                code, out = self.main("--dump", path)
                self.assert_clean_error(
                    code, out, "--dump không được ghi vào trong repo"
                )
                self.assertFalse(os.path.exists(path))
                self.assertFalse(os.path.exists(self.reviews))
                self.assertEqual(self.calls, [])

    def test_dump_relative_path_resolving_into_repo_is_refused(self):
        cwd = os.getcwd()
        os.chdir(os.path.join(self.repo, "evidence"))
        try:
            code, out = self.main("--dump", "dump.txt")
        finally:
            os.chdir(cwd)
        self.assert_clean_error(code, out, "--dump không được ghi vào trong repo")
        self.assertEqual(os.listdir(os.path.join(self.repo, "evidence")), [])
        self.assertEqual(self.calls, [])

    def test_extended_length_prefix_spelling_inside_repo_is_refused(self):
        # CR2-12: realpath trên Windows có thể trả về \\?\C:\…; đường dẫn đó vẫn là trong repo
        target = os.path.join(self.repo, "dump.txt")
        real_realpath = os.path.realpath

        def prefixed(path):
            resolved = real_realpath(path)
            return "\\\\?\\" + resolved if path == target else resolved

        with mock.patch.object(fr.os.path, "realpath", side_effect=prefixed):
            code, out = self.main("--dump", target)
        self.assert_clean_error(code, out, "--dump không được ghi vào trong repo")
        self.assertFalse(os.path.exists(target))
        self.assertEqual(self.calls, [])

    def test_dump_to_a_directory_is_refused_before_any_network_call(self):
        code, out = self.main("--dump", self.tmp)
        self.assert_clean_error(code, out, "thư mục")
        self.assertEqual(self.calls, [])

    def test_dump_outside_repo_gets_masked_full_text(self):
        self.content = "Gọi 0912 345 678\nkhông được, mất 1.500.000"
        # thư mục cạnh repo có cùng tiền tố tên vẫn là "ngoài repo"
        os.mkdir(self.repo + "-ngoai")
        dump = os.path.join(self.repo + "-ngoai", "dump.txt")
        for args in (
            ("--dump", dump),
            ("--refresh", "--dump", dump),
            ("--dump", dump, "--refresh"),
        ):
            with self.subTest(args=args[::2]):
                code, out = self.main(*args)
                self.assertEqual(code, 0, out)
                with open(dump, encoding="utf-8") as f:
                    lines = f.read().splitlines()
                self.assertEqual(len(lines), 150)
                self.assertTrue(
                    lines[0].startswith("100 [MoMo 3 sao] t | Gọi [đã che] không được"),
                    lines[0],
                )
                self.assertIn("1.500.000", lines[0])
                self.assertNotIn("0912", "".join(lines))

    def test_partial_dump_leaves_out_the_failed_app(self):
        self.broken = {1: (2, "raise")}
        dump = os.path.join(self.tmp, "dump.txt")
        code, out = self.main("--refresh", "--allow-partial", "--dump", dump)
        self.assertEqual(code, 0, out)
        with open(dump, encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(len(text.splitlines()), 100)
        self.assertNotIn("Techcombank", text)

    def test_dump_write_failure_is_a_clean_error_and_writes_no_reviews(self):
        before = self.seed()
        code, out = self.main(
            "--refresh", "--dump", os.path.join(self.tmp, "khong-co", "dump.txt")
        )
        self.assert_clean_error(code, out, "không ghi được", "dump.txt")
        self.assertEqual(self.snapshot(), before)


class TestInRepo(unittest.TestCase):
    """Chỉ hỏi đường dẫn, không ghi gì."""

    def test_default_root_is_this_repository(self):
        self.assertEqual(os.path.realpath(fr.ROOT), os.path.realpath(ROOT))
        self.assertTrue(fr.in_repo(os.path.join(ROOT, "x.txt")))
        self.assertTrue(fr.in_repo(ROOT))
        self.assertFalse(fr.in_repo(os.path.join(os.path.dirname(ROOT), "x.txt")))

    def test_failed_string_comparison_falls_back_to_the_file_check(self):
        # khác ổ đĩa / kiểu UNC: so chuỗi không được, nhưng file trong repo vẫn phải bị nhận ra, file ngoài thì không
        with mock.patch.object(
            fr.os.path, "commonpath", side_effect=ValueError("khác ổ đĩa")
        ):
            self.assertTrue(fr.in_repo(os.path.join(ROOT, "x.txt")))
            self.assertFalse(fr.in_repo(os.path.dirname(ROOT)))


class TestApplyLabels(Base):
    def setUp(self):
        super().setUp()
        self.draft = os.path.join(self.tmp, "draft.csv")
        self.rows_before = [
            row(
                ma="1",
                app="MoMo",
                trich="anh Nam và chị Lan nói khó xem",
                human_verified="false",
            ),
            row(
                ma="2",
                app="MoMo",
                nhan="khac",
                trich="anh Nam kiểm",
                nguoi_gan="Người A",
                human_verified="true",
            ),
            row(
                ma="3",
                app="MoMo",
                nhan="khac",
                trich="anh Nam",
                nguoi_gan="Người B",
                human_verified="true ",
            ),
            row(
                ma="4",
                app="MoMo",
                nhan="khac",
                trich="anh Nam",
                nguoi_gan="Người C",
                human_verified="TRUE",
            ),
            row(
                ma="5",
                app="MoMo",
                nhan="khac",
                trich="anh Nam",
                nguoi_gan="Người D",
                human_verified=" true",
            ),
            row(ma="6", app="MoMo", nhan="", trich="không có trong nháp"),
        ]
        self.before = self.seed(self.rows_before)

    def apply(self, text=None):
        if text is not None:
            self.put(self.draft, text)
        return self.main("--apply-labels", self.draft)

    def assert_refused(self, result, *words):
        self.assert_clean_error(*result, *words)
        self.assertEqual(self.snapshot(), self.before)
        self.assertEqual(self.calls, [])

    def test_labels_unverified_rows_masks_names_and_never_touches_verified_rows(self):
        drafts = "ma,nhan,che\n" + "".join(
            "%d,kho_hieu_gd, Nam ;Lan;\n" % i for i in range(1, 6)
        )
        code, out = self.apply(drafts.encode("utf-8-sig"))
        self.assertEqual(code, 0, out)
        self.assertIn("1/6 dòng", out)
        rows = self.rows()
        self.assertEqual(
            (
                rows[0]["nhan"],
                rows[0]["nguoi_gan"],
                rows[0]["human_verified"],
                rows[0]["trich"],
            ),
            (
                "kho_hieu_gd",
                "Claude (nháp)",
                "false",
                "anh [tên] và chị [tên] nói khó xem",
            ),
        )
        self.assertEqual(rows[1:], self.rows_before[1:])
        self.assertEqual(self.snapshot()[1], LOG_SENTINEL)
        self.assertEqual(self.calls, [])

    def test_missing_draft_file(self):
        self.assert_refused(self.apply(), "không thấy file nhãn nháp")

    def test_draft_path_is_a_directory(self):
        os.mkdir(self.draft)
        self.assert_refused(self.apply(), "không thấy file nhãn nháp")

    def test_draft_missing_each_column(self):
        for header, missing in (
            ("nhan,che", "ma"),
            ("ma,che", "nhan"),
            ("ma,nhan", "che"),
        ):
            with self.subTest(missing=missing):
                self.assert_refused(
                    self.apply(header + "\nkhac,khac\n"), "thiếu cột: %s" % missing
                )

    def test_empty_draft_file(self):
        self.assert_refused(self.apply(""), "thiếu cột: ma,nhan,che")

    def test_draft_undecodable(self):
        self.assert_refused(
            self.apply(b"ma,nhan,che\n1,\xff\xfe,\n"), "không đọc được file nhãn nháp"
        )

    def test_draft_blank_code(self):
        self.assert_refused(self.apply("ma,nhan,che\n ,khac,\n"), "dòng không có mã")

    def test_draft_duplicate_code(self):
        self.assert_refused(
            self.apply("ma,nhan,che\n1,khac,\n 1 ,kho_hieu_gd,\n"), "mã trùng: 1"
        )

    def test_unknown_code(self):
        self.assert_refused(
            self.apply("ma,nhan,che\n1,khac,\n77,khac,\n"),
            "mã không có trong reviews.csv",
            "77",
        )

    def test_unknown_label(self):
        self.assert_refused(
            self.apply("ma,nhan,che\n1,nhan_bay,\n"), "nhãn lạ", "nhan_bay"
        )

    def test_reviews_missing_a_required_column(self):
        for column in ("ma", "human_verified", "trich"):
            with self.subTest(column=column):
                columns = [c for c in count.COLUMNS if c != column]
                self.put(self.reviews, csv_of(self.rows_before, columns))
                self.before = self.snapshot()
                self.assert_refused(
                    self.apply("ma,nhan,che\n1,khac,\n"), "phải có đúng các cột"
                )

    def test_reviews_missing(self):
        os.remove(self.reviews)
        self.before = self.snapshot()
        self.assert_refused(
            self.apply("ma,nhan,che\n1,khac,\n"), "không thấy reviews.csv"
        )

    def test_reviews_with_duplicate_code(self):
        self.before = self.seed([row(ma="1"), row(ma="1 ")])
        self.assert_refused(self.apply("ma,nhan,che\n1,khac,\n"), "mã trùng")

    def test_write_failure_is_a_clean_error(self):
        with mock.patch.object(
            fr.os, "replace", side_effect=PermissionError("đang mở")
        ):
            result = self.apply("ma,nhan,che\n1,khac,\n")
        self.assert_refused(result, "không ghi được", "đang mở")


class TestMainArguments(Base):
    def test_bad_arguments_print_usage_exit_2_and_do_nothing(self):
        before = self.seed()
        for args in (
            ["--bad"],
            ["--dump"],
            ["--dump", "a", "b"],
            ["--apply-labels"],
            ["--apply-labels", "a", "b"],
            ["--apply-labels", "a", "--refresh"],
            ["--refresh", "--apply-labels", "a"],
            ["--refresh", "x"],
            ["--allow-partial", "--bad"],
        ):
            with self.subTest(args=args):
                code, out = self.main(*args)
                self.assertEqual(code, 2, out)
                self.assertIn("--allow-partial", out)  # in hướng dẫn dùng
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
