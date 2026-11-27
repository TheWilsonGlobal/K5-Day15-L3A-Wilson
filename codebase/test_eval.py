"""Test bộ câu thử, đáp án và bộ chấm. Model được thay bằng câu trả lời dựng sẵn; file tạm, không đụng eval/.

python -m unittest discover -s codebase -p "test_*.py"
"""

import contextlib
import csv
import glob
import io
import json
import os
import shutil
import sys
import tempfile
import unicodedata
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for folder in (HERE, os.path.join(ROOT, "eval")):
    if folder not in sys.path:
        sys.path.insert(0, folder)
os.environ["MODEL_PROVIDER"] = "fake"

import add_cases  # noqa: E402  # import sau khi đặt sys.path và MODEL_PROVIDER=fake
import agent  # noqa: E402  # import sau khi đặt sys.path và MODEL_PROVIDER=fake
import grade  # noqa: E402  # import sau khi đặt sys.path và MODEL_PROVIDER=fake
import oracle  # noqa: E402  # import sau khi đặt sys.path và MODEL_PROVIDER=fake
import run_eval  # noqa: E402  # import sau khi đặt sys.path và MODEL_PROVIDER=fake
import tracing  # noqa: E402  # import sau khi đặt sys.path và MODEL_PROVIDER=fake
from test_tools import TRUTH, ModelStub  # noqa: E402  # import sau khi đặt sys.path và MODEL_PROVIDER=fake

with open(
    os.path.join(ROOT, "eval", "benchmark.csv"), encoding="utf-8-sig", newline=""
) as f:
    BENCH = {r["id"]: r for r in csv.DictReader(f)}
with open(add_cases.DRAFT, encoding="utf-8-sig", newline="") as f:
    DRAFT = {r["id"]: r for r in csv.DictReader(f)}
ALL = dict(DRAFT, **BENCH)  # câu đã trong bộ + câu soạn sẵn
MAIN = [
    "C%02d" % n for n in range(1, 11)
]  # bộ câu thử ghi ở đầu trace của lượt trong thư mục tạm
OLD_MTIME = 1_000_000_000  # mốc cũ để thấy file có bị ghi lại hay không
MACHINE_NOTE = r"grade\.py (đạt|trượt: .+) \[mã [0-9a-f]{8}\]"
OCT_GROUPS = [
    "  Mua sắm: 21.788.000đ (10 giao dịch)",
    "  Hoá đơn: 5.402.000đ (3 giao dịch)",
    "  Không rõ: 5.173.000đ (10 giao dịch)",
    "  Ăn uống: 1.747.000đ (29 giao dịch)",
    "  Sức khoẻ: 1.701.000đ (4 giao dịch)",
    "  Học tập: 1.546.000đ (3 giao dịch)",
    "  Đi lại: 1.174.000đ (18 giao dịch)",
    "  Giải trí: 530.000đ (3 giao dịch)",
]


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def write_bytes(path, data):
    with open(path, "wb") as f:
        f.write(data)


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def temp_dir(test):
    path = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, path)
    return path


def leaked_inputs(folder, rows):
    """→ [(tên file, mã câu)]: nguyên câu hỏi nằm trong một file nguồn (không phải test) của thư mục. So theo NFC."""
    found = []
    for path in sorted(glob.glob(os.path.join(folder, "*.py"))):
        if os.path.basename(path).startswith("test_"):
            continue
        with open(path, encoding="utf-8-sig") as f:
            code = unicodedata.normalize("NFC", f.read())
        found += [
            (os.path.basename(path), r["id"])
            for r in rows
            if unicodedata.normalize("NFC", r["input"]) in code
        ]
    return found


def ideal_plan(case):
    """Kế hoạch mà một model hiểu đúng câu hỏi sẽ trả."""
    plan = dict(case["plan"], intent=case["plan"]["intent"][0])
    if (
        plan["intent"] == "noi_ban"
    ):  # đáp án không so tên nơi bán nguyên văn, nhưng kế hoạch phải có
        plan["merchant"] = "cơm cô ba"
    if plan["intent"] == "tu_choi":
        words = (
            case["must_contain"][0] if case["must_contain"] else "không tư vấn đầu tư"
        )
        plan["reason"] = next(k for k, v in agent.REFUSALS.items() if words in v)
    return plan


class TestBenchmark(unittest.TestCase):
    def test_oracle_json_is_current_and_matches_benchmark_ids(self):
        with open(oracle.ORACLE_JSON, encoding="utf-8") as f:
            saved = json.load(f)["cases"]
        self.assertEqual(saved, json.loads(json.dumps(oracle.cases())))
        self.assertTrue(set(saved) <= set(BENCH))

    def test_inputs_are_not_hardcoded_in_prompts(self):
        sources = {os.path.basename(p) for p in glob.glob(os.path.join(HERE, "*.py"))}
        self.assertTrue({"agent.py", "ai.py", "app.py", "tools.py"} <= sources, sources)
        rows = list(BENCH.values()) + list(
            DRAFT.values()
        )  # cả hai file, kể cả khi trùng mã câu
        self.assertTrue(BENCH and DRAFT and all(r["input"].strip() for r in rows))
        self.assertEqual(leaked_inputs(HERE, rows), [])

    def test_leak_guard_sees_every_source_file_both_sets_and_decomposed_text(self):
        tmp = temp_dir(self)
        bench, draft = BENCH["C01"], DRAFT["C18"]
        planted = {
            "app.py": unicodedata.normalize("NFD", bench["input"]),
            "moi.py": draft["input"],
            "test_bo_qua.py": bench["input"],
        }
        self.assertNotEqual(
            planted["app.py"], unicodedata.normalize("NFC", bench["input"])
        )
        for name, text in planted.items():
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as f:
                f.write("VI_DU = '%s'\n" % text)
        self.assertEqual(
            leaked_inputs(tmp, [bench, draft]), [("app.py", "C01"), ("moi.py", "C18")]
        )
        decomposed = dict(draft, input=unicodedata.normalize("NFD", draft["input"]))
        self.assertEqual(leaked_inputs(tmp, [decomposed]), [("moi.py", "C18")])

    def test_types(self):
        self.assertTrue(
            {r["type"] for r in BENCH.values()} == {"thuong", "kho", "tu_choi"}
        )
        for case_id, case in oracle.cases(ALL).items():
            self.assertEqual(
                "tu_choi_dung" in case["metrics"],
                ALL[case_id]["type"] == "tu_choi",
                case_id,
            )

    def test_every_draft_case_has_an_answer_and_review_source_exists(self):
        self.assertEqual(set(oracle.draft_cases()), set(DRAFT))
        with open(
            os.path.join(ROOT, "evidence", "reviews.csv"),
            encoding="utf-8-sig",
            newline="",
        ) as f:
            reviews = {r["ma"] for r in csv.DictReader(f)}
        for row in DRAFT.values():
            if row["source"].startswith("data_that"):
                self.assertIn(row["source"].split()[-1], reviews, row["id"])


class TestOracle(unittest.TestCase):
    def test_c01_requires_every_october_category_line(self):
        must = oracle.cases()["C01"]["must_contain"]
        self.assertIn("39.061.000đ (80 giao dịch)", must[0])
        self.assertEqual(must[1:], OCT_GROUPS)

    def test_c04_requires_the_partial_month_warning(self):
        self.assertIn(
            "tháng 11/2026 mới có dữ liệu đến 27/11/2026",
            oracle.cases()["C04"]["must_contain"],
        )

    def test_c16_requires_the_full_transaction_row(self):
        must = oracle.cases({"C16"})["C16"]["must_contain"]
        self.assertEqual(must, ["T0173", "T0173 · 02/11/2026 · 133.000đ"])

    def test_c16_id_comes_from_tx_id_of(self):
        with mock.patch.object(oracle, "tx_id_of", return_value="T9999") as lookup:
            must = oracle.cases({"C16"})["C16"]["must_contain"]
        lookup.assert_called_with("2026-11-02", 133000)
        self.assertEqual(must, ["T9999", "T9999 · 02/11/2026 · 133.000đ"])

    def test_tx_id_of_needs_exactly_one_match(self):
        self.assertEqual(oracle.tx_id_of("2026-11-02", 133000), "T0173")
        with self.assertRaises(ValueError):
            oracle.tx_id_of("2026-11-02", 133001)
        row = next(
            r
            for r in oracle.spending("2026-11-02", "2026-11-02")
            if r["tx_id"] == "T0173"
        )
        with mock.patch.object(
            oracle, "spending", return_value=[row, dict(row, tx_id="T9999")]
        ):
            with self.assertRaisesRegex(ValueError, "thấy 2"):
                oracle.tx_id_of("2026-11-02", 133000)

    def old_answers(self):
        tmp = temp_dir(self)
        path = os.path.join(tmp, "oracle.json")
        write_bytes(path, b'{"cu": 1}\n')
        return tmp, path

    def assert_old_answers_kept(self, tmp, path):
        self.assertEqual(read_bytes(path), b'{"cu": 1}\n')
        self.assertEqual(os.listdir(tmp), ["oracle.json"])

    def test_write_json_writes_the_cases(self):
        tmp, path = self.old_answers()
        oracle.write_json(path)
        self.assertEqual(
            json.loads(read_bytes(path))["cases"],
            json.loads(json.dumps(oracle.cases())),
        )
        self.assertEqual(os.listdir(tmp), ["oracle.json"])

    def test_write_json_keeps_the_old_file_when_cases_fails(self):
        tmp, path = self.old_answers()
        with mock.patch.object(
            oracle, "cases", side_effect=ValueError("hỏng giữa chừng")
        ):
            with self.assertRaises(ValueError):
                oracle.write_json(path)
        self.assert_old_answers_kept(tmp, path)

    def test_write_json_keeps_the_old_file_when_replace_fails(self):
        tmp, path = self.old_answers()
        with mock.patch.object(os, "replace", side_effect=PermissionError("đang mở")):
            with self.assertRaises(PermissionError):
                oracle.write_json(path)
        self.assert_old_answers_kept(tmp, path)


class TestAddCases(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        self.bench, self.draft = (
            os.path.join(tmp, "bench.csv"),
            os.path.join(tmp, "draft.csv"),
        )
        head = "id,input,expected,pass_criterion,type,source\r\n"
        with open(self.bench, "w", encoding="utf-8-sig", newline="") as f:
            f.write(head + "C01,a,e,p,kho,tu_viet\r\n")
        with open(self.draft, "w", encoding="utf-8-sig", newline="") as f:
            f.write(
                head
                + 'C11,"b, c",e,p,kho,data_that: review 1\r\nC12,d,e,p,kho,tu_viet\r\n'
                + "C13,g,e,p,kho,tu_viet\r\nC14,h,e,p,kho,tu_viet\r\n"
            )

    def read(self):
        return read_bytes(self.bench)

    def add_drafts(self, *lines):
        with open(self.draft, "a", encoding="utf-8", newline="") as f:
            f.writelines(line + "\r\n" for line in lines)

    def test_rejects_an_id_without_an_oracle_answer_before_writing(self):
        self.add_drafts("C99,z,e,p,kho,data_that: review 1")
        before = self.read()
        for ids in (["C99"], ["C11", "C99"]):
            with self.assertRaisesRegex(ValueError, "chưa có đáp án.*C99"):
                add_cases.add(ids, self.bench, self.draft)
            self.assertEqual(self.read(), before, ids)

    def test_rejects_two_new_cases_with_the_same_question_before_writing(self):
        self.add_drafts(
            "C15,trùng nhau,e,p,kho,data_that: review 1",
            "C16,trùng nhau,e,p,kho,data_that: review 2",
        )
        before = self.read()
        with self.assertRaisesRegex(ValueError, "trùng câu hỏi với nhau: trùng nhau"):
            add_cases.add(["C15", "C16"], self.bench, self.draft)
        self.assertEqual(self.read(), before)
        self.assertEqual(add_cases.add(["C15"], self.bench, self.draft), (2, 1))

    def test_failed_replace_leaves_the_benchmark_untouched(self):
        before = self.read()
        with mock.patch.object(os, "replace", side_effect=PermissionError("đang mở")):
            with self.assertRaises(PermissionError):
                add_cases.add(["C11"], self.bench, self.draft)
        self.assertEqual(self.read(), before)
        self.assertEqual(
            sorted(os.listdir(os.path.dirname(self.bench))), ["bench.csv", "draft.csv"]
        )

    def test_appends_and_keeps_old_bytes(self):
        before = self.read()
        self.assertEqual(add_cases.add(["C11"], self.bench, self.draft), (2, 1))
        self.assertTrue(self.read().startswith(before))
        self.assertEqual(
            [r["input"] for r in add_cases.read(self.bench)[1]], ["a", "b, c"]
        )

    def test_rejects_bad_requests_without_writing(self):
        before = self.read()
        for ids in ([], ["C99"], ["C12"], ["C11", "C11"], ["C11", "C12", "C13"]):
            with self.assertRaises(ValueError):
                add_cases.add(ids, self.bench, self.draft)
        self.assertEqual(self.read(), before)
        add_cases.add(["C11"], self.bench, self.draft)
        with self.assertRaises(ValueError):
            add_cases.add(["C11"], self.bench, self.draft)

    def test_rejects_a_new_question_that_repeats_one_already_in_the_benchmark(self):
        # C01 trong bộ có câu hỏi "a"; câu nháp mới C15 cũng là "a" thì phải bị từ chối, không ghi gì
        self.add_drafts("C15,a,e,p,kho,data_that: review 1")
        before = self.read()
        with self.assertRaisesRegex(ValueError, "trùng câu hỏi đã có: a"):
            add_cases.add(["C15"], self.bench, self.draft)
        self.assertEqual(self.read(), before)


class GraderCase(unittest.TestCase):
    """Một lượt chạy trong thư mục tạm: run-9.csv, traces/run-9.jsonl, answers.json."""

    def setUp(self):
        self.tmp = temp_dir(self)
        os.makedirs(os.path.join(self.tmp, "traces"))
        self.use("run-9")
        self.answers = os.path.join(self.tmp, "answers.json")
        with mock.patch.object(oracle, "benchmark_ids", lambda: set(ALL)):
            oracle.write_json(self.answers)
        for target, name, value in (
            (grade, "ROOT", self.tmp),
            (oracle, "ORACLE_JSON", self.answers),
            (run_eval, "TRACES", os.path.join(self.tmp, "traces")),
        ):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def use(self, name):
        self.name = name
        self.path = os.path.join(self.tmp, name + ".csv")
        self.trace_path = os.path.join(self.tmp, "traces", name + ".jsonl")

    def make_run(self, plans, edit=None, bench=None, stub=ModelStub):
        """Chạy các câu qua đúng bộ chạy của khung, ghi file lượt và trace vào thư mục tạm."""
        rows, events = [], []
        if bench:
            events.append({"kind": "bench", "ids": bench, "case": ""})
        for case_id, plan in plans.items():
            with mock.patch.object(
                agent, "call_model", tracing.model_call(stub(plan).__call__)
            ):
                row, trace = run_eval.call_case(
                    agent.answer, tracing, case_id, ALL[case_id]["input"]
                )
            self.assertEqual(row["error"], "")
            row.update(
                {
                    k: ALL[case_id][k]
                    for k in ("id", "type", "input", "expected", "pass_criterion")
                }
            )
            row.update({"run_id": self.name + "@test", "pass": "", "ghi_chu": ""})
            rows.append(row)
            events += [dict(e, case=case_id) for e in trace]
        if edit:
            edit(rows)
        run_eval.write_csv(self.path, run_eval.OUT_COLS, rows)
        with open(self.trace_path, "w", encoding="utf-8") as f:
            f.writelines(
                json.dumps(e, ensure_ascii=False, default=str) + "\n" for e in events
            )

    def ideal_run(self, ids=MAIN, **kwargs):
        cases = oracle.cases(ALL)
        self.make_run({i: ideal_plan(cases[i]) for i in ids}, **kwargs)

    def grade(self, **flags):
        rows, stats, manual = grade.grade_file(self.path, **flags)
        return {r["id"]: r for r in rows}, stats, manual

    def row(self, case_id):
        return next(r for r in read_rows(self.path) if r["id"] == case_id)

    def set_row(self, case_id, values):
        rows = read_rows(self.path)
        next(r for r in rows if r["id"] == case_id).update(values)
        run_eval.write_csv(self.path, list(rows[0]), rows)

    def edit_answers(self, edit):
        saved = json.loads(read_bytes(self.answers))
        edit(saved["cases"])
        write_bytes(self.answers, json.dumps(saved, ensure_ascii=False).encode("utf-8"))

    def drop_trace_of(self, case_id):
        with open(self.trace_path, encoding="utf-8") as f:
            kept = [line for line in f if json.loads(line)["case"] != case_id]
        with open(self.trace_path, "w", encoding="utf-8") as f:
            f.writelines(kept)

    def assert_untouched(self, before):
        self.assertEqual(read_bytes(self.path), before)
        self.assertEqual([n for n in os.listdir(self.tmp) if n.endswith(".tmp")], [])


def tamper_c01(rows):
    """Sửa tổng tiền trong output đã ghi của C01 (số không còn khớp công cụ)."""
    row = next(r for r in rows if r["id"] == "C01")
    assert "39.061.000đ" in row["output"]
    row["output"] = row["output"].replace("39.061.000đ", "39.062.000đ")


class TestGrader(GraderCase):
    def test_ideal_model_passes_every_case_and_other_columns_are_kept(self):
        self.make_run({i: ideal_plan(c) for i, c in oracle.cases(ALL).items()})
        with open(self.path, encoding="utf-8-sig", newline="") as f:
            before = list(csv.DictReader(f))
        rows, _, manual = self.grade()
        self.assertEqual(
            {i: r["ghi_chu"] for i, r in rows.items() if r["pass"] != "1"}, {}
        )
        self.assertEqual(manual, [])
        for old in before:
            keep = [k for k in old if k not in ("pass", "ghi_chu")]
            self.assertEqual([rows[old["id"]][k] for k in keep], [old[k] for k in keep])
        self.assertTrue(grade.verdict(list(rows.values()))[0])

    def test_wrong_period_fails_plan_and_answer_but_not_numbers(self):
        plan = dict(
            ideal_plan(oracle.cases()["C01"]),
            **{"from": "2026-09-01", "to": "2026-09-30"},
        )
        self.make_run({"C01": plan})
        note = self.grade()[0]["C01"]["ghi_chu"]
        self.assertIn("dung_ke_hoach (", note)
        self.assertIn("dung_dap_an (", note)
        self.assertNotIn("so_khop_cong_cu (", note)

    def test_edited_number_fails_number_match(self):
        self.make_run(
            {"C01": ideal_plan(oracle.cases()["C01"])},
            edit=lambda rows: rows[0].update(
                output=rows[0]["output"].replace("39.061.000đ", "39.062.000đ")
            ),
        )
        rows = self.grade()[0]
        self.assertIn("so_khop_cong_cu (", rows["C01"]["ghi_chu"])
        self.assertFalse(grade.verdict(list(rows.values()))[0])

    def test_answering_a_forbidden_request_fails(self):
        self.make_run(
            {"C09": {"intent": "liet_ke", "from": "2026-11-01", "to": "2026-11-27"}}
        )
        row = self.grade()[0]["C09"]
        self.assertEqual(row["pass"], "0")
        self.assertIn("đã gọi công cụ", row["ghi_chu"])

    def test_filled_pass_is_not_overwritten(self):
        self.make_run(
            {"C03": ideal_plan(oracle.cases()["C03"])},
            edit=lambda rows: rows[0].update({"pass": "0", "ghi_chu": "người chấm"}),
        )
        row = self.grade()[0]["C03"]
        self.assertEqual((row["pass"], row["ghi_chu"]), ("0", "người chấm"))

    def test_swapped_category_amounts_fail_the_c01_answer(self):
        def swap(rows):
            out = rows[0]["output"]
            self.assertIn("Mua sắm: 21.788.000đ", out)
            self.assertIn("Hoá đơn: 5.402.000đ", out)
            rows[0]["output"] = out.replace(
                "Mua sắm: 21.788.000đ", "Mua sắm: 5.402.000đ"
            ).replace("Hoá đơn: 5.402.000đ", "Hoá đơn: 21.788.000đ")

        self.make_run({"C01": ideal_plan(oracle.cases()["C01"])}, edit=swap)
        self.assertIn(
            "dung_dap_an (thiếu:   Mua sắm: 21.788.000đ",
            self.grade()[0]["C01"]["ghi_chu"],
        )

    def test_dropped_partial_month_warning_fails_the_c04_answer(self):
        def drop(rows):
            lines = rows[0]["output"].split("\n")
            kept = [line for line in lines if not line.startswith("Chú ý:")]
            self.assertEqual(len(kept), len(lines) - 1)
            rows[0]["output"] = "\n".join(kept)

        self.make_run({"C04": ideal_plan(oracle.cases()["C04"])}, edit=drop)
        self.assertIn(
            "dung_dap_an (thiếu: tháng 11/2026 mới có dữ liệu",
            self.grade()[0]["C04"]["ghi_chu"],
        )

    def test_dropped_amount_fails_the_c16_answer(self):
        def drop(rows):
            self.assertIn("T0173 · 02/11/2026 · 133.000đ", rows[0]["output"])
            rows[0]["output"] = rows[0]["output"].replace(
                "T0173 · 02/11/2026 · 133.000đ", "T0173 · 02/11/2026"
            )

        self.make_run({"C16": ideal_plan(oracle.cases(ALL)["C16"])}, edit=drop)
        self.assertIn(
            "dung_dap_an (thiếu: T0173 · 02/11/2026 · 133.000đ",
            self.grade()[0]["C16"]["ghi_chu"],
        )


class TestGraderBadInput(GraderCase):
    def corrupt(self, mutate):
        """Lượt có dòng chưa chấm (nên bình thường sẽ ghi file), rồi làm hỏng bảng."""
        self.ideal_run(["C01", "C03"])
        with open(self.path, encoding="utf-8-sig", newline="") as f:
            table = list(csv.reader(f))
        mutate(table)
        with open(self.path, "w", encoding="utf-8-sig", newline="") as f:
            csv.writer(f).writerows(table)
        return read_bytes(self.path)

    def check_rejected(self, mutate, message):
        before = self.corrupt(mutate)
        for flags in ({}, {"force": True}, {"force_human": True}):
            with self.assertRaisesRegex(SystemExit, message):
                self.grade(**flags)
            self.assert_untouched(before)

    def test_extra_cell_is_rejected_and_nothing_is_written(self):
        self.check_rejected(lambda t: t[-1].append("ghi thêm"), "C03.*thừa ô")

    def test_short_row_is_rejected_and_nothing_is_written(self):
        self.check_rejected(lambda t: t[-1].pop(), "C03.*thiếu ô")

    def test_duplicate_column_is_rejected_and_nothing_is_written(self):
        self.check_rejected(lambda t: [r.append(r[0]) for r in t], "cột trùng tên")

    def test_each_missing_required_column_is_rejected_and_nothing_is_written(self):
        for column in ("id", "input", "output", "pass", "ghi_chu"):
            with self.subTest(column=column):

                def drop(table):
                    at = table[0].index(column)
                    for r in table:
                        del r[at]

                self.check_rejected(drop, "thiếu cột: %s " % column)

    def test_semicolon_file_is_rejected_and_nothing_is_written(self):
        def semicolons(table):
            table[:] = [[";".join(r)] for r in table]

        self.check_rejected(semicolons, "thiếu cột")

    def test_failed_replace_leaves_the_run_file_untouched(self):
        self.ideal_run(["C01"])
        before = read_bytes(self.path)
        with mock.patch.object(os, "replace", side_effect=PermissionError("đang mở")):
            with self.assertRaises(PermissionError):
                self.grade()
        self.assert_untouched(before)

    def test_missing_trace_stops_without_writing(self):
        self.ideal_run(["C01"])
        os.remove(self.trace_path)
        before = read_bytes(self.path)
        with self.assertRaisesRegex(SystemExit, "Không có trace"):
            self.grade()
        self.assert_untouched(before)

    def test_run_fake_is_never_graded(self):
        self.use("run-fake")
        self.ideal_run(["C01"])
        before = read_bytes(self.path)
        with self.assertRaisesRegex(SystemExit, "chỉ chấm được lượt có gọi agent"):
            self.grade()
        self.assert_untouched(before)

    def test_trace_from_another_run_stops_without_writing(self):
        self.ideal_run(["C01", "C03"])
        self.drop_trace_of("C03")
        before = read_bytes(self.path)
        with self.assertRaisesRegex(SystemExit, "Trace không có câu C03"):
            self.grade()
        self.assert_untouched(before)


class TestHumanRows(GraderCase):
    def setUp(self):
        super().setUp()
        self.ideal_run(["C01", "C03"])
        self.grade()
        self.auto = self.row("C01")["ghi_chu"]

    def reviewed(self):
        """Các kiểu dòng người rà, tính từ ghi chú máy của một câu đạt."""
        return {
            "note trống, đã điền pass": ("0", ""),
            "đổi pass, giữ ghi chú máy": ("0", self.auto),
            "viết thêm sau ghi chú máy": ("1", self.auto + " | người rà: ổn"),
            "viết thêm không có dấu ngăn": ("1", self.auto + " người rà"),
            "viết trước ghi chú máy": ("0", "người rà: sai | " + self.auto),
            "chữ tự do nhắc grade.py": ("0", "sai nhóm; grade.py không kiểm bảng nhóm"),
            "ghi chú kiểu cũ không có mã": ("0", "grade.py đạt"),
        }

    def test_machine_notes_end_with_a_code(self):
        self.assertRegex(self.auto, r"^grade\.py đạt \[mã [0-9a-f]{8}\]$")
        self.set_row("C01", {"output": "khác hẳn", "pass": "", "ghi_chu": ""})
        self.grade()
        self.assertRegex(
            self.row("C01")["ghi_chu"], r"^grade\.py trượt: .+ \[mã [0-9a-f]{8}\]$"
        )

    def test_force_keeps_human_rows(self):
        for name, (passed, note) in self.reviewed().items():
            with self.subTest(name):
                self.set_row("C01", {"pass": passed, "ghi_chu": note})
                before = read_bytes(self.path)
                rows = self.grade(force=True)[0]
                self.assertTrue(rows["C01"].human)
                self.assertFalse(rows["C03"].human)
                self.assert_untouched(before)

    def test_force_human_regrades_and_keeps_the_old_note_verbatim(self):
        for name, (passed, note) in self.reviewed().items():
            with self.subTest(name):
                self.set_row("C01", {"pass": passed, "ghi_chu": note})
                self.grade(force_human=True)
                row = self.row("C01")
                self.assertEqual(row["pass"], "1")
                self.assertTrue(row["ghi_chu"].startswith(note), row["ghi_chu"])
                added = row["ghi_chu"][len(note) :]
                if not note:
                    self.assertRegex(added, "^" + MACHINE_NOTE + "$")
                elif note.endswith(self.auto):
                    self.assertEqual(
                        added, ""
                    )  # ghi chú đã đúng kết quả mới: không nối lặp
                else:
                    self.assertRegex(added, r"^ \| " + MACHINE_NOTE + "$")
                before = read_bytes(self.path)
                self.grade(force_human=True)
                self.assert_untouched(before)  # chấm lại lần nữa không nối thêm gì

    def test_force_replaces_a_machine_note_without_appending(self):
        self.edit_answers(
            lambda cases: cases["C01"]["must_contain"].append("không có chuỗi này")
        )
        self.grade(force=True)
        row = self.row("C01")
        self.assertEqual(row["pass"], "0")
        self.assertRegex(
            row["ghi_chu"], r"^grade\.py trượt: dung_dap_an .+ \[mã [0-9a-f]{8}\]$"
        )
        self.assertNotIn("grade.py đạt", row["ghi_chu"])

    def test_blank_pass_keeps_the_human_text(self):
        note = "xem lại: grade.py từng cho đạt, tôi nghi"
        self.set_row("C01", {"pass": "", "ghi_chu": note})
        self.grade()
        self.assertTrue(
            self.row("C01")["ghi_chu"].startswith(note + " | grade.py đạt [mã ")
        )

    def test_runner_note_is_not_a_human_note(self):
        self.set_row("C01", {"pass": "", "ghi_chu": "output rỗng"})
        self.grade()
        self.edit_answers(
            lambda cases: cases["C01"]["must_contain"].append("không có chuỗi này")
        )
        rows = self.grade(force=True)[0]
        self.assertFalse(rows["C01"].human)
        self.assertTrue(
            self.row("C01")["ghi_chu"].startswith("output rỗng | grade.py trượt: ")
        )

    def test_unchanged_file_is_not_rewritten(self):
        self.set_row("C03", {"pass": "0", "ghi_chu": "người rà"})
        os.utime(self.path, (OLD_MTIME, OLD_MTIME))
        for flags in ({}, {"force": True}):
            with mock.patch.object(os, "replace", wraps=os.replace) as replace:
                self.grade(**flags)
            replace.assert_not_called()
            self.assertEqual(os.stat(self.path).st_mtime, OLD_MTIME, flags)


class TestNumberCheck(GraderCase):
    def test_tampered_number_on_a_human_row_is_still_checked(self):
        self.ideal_run(edit=tamper_c01, bench=MAIN)
        self.set_row("C01", {"pass": "1", "ghi_chu": "người rà: số đúng"})
        for flags in ({}, {"force": True}):
            with self.subTest(**flags):
                rows = self.grade(**flags)[0]
                self.assertEqual(rows["C01"]["pass"], "1")
                self.assertTrue(rows["C01"].numbers)
                self.assertEqual(
                    [i for i, r in rows.items() if r.numbers != ""], ["C01"]
                )
                self.assertIs(grade.verdict(list(rows.values()))[0], False)

    def test_case_without_an_oracle_answer_is_still_checked(self):
        self.ideal_run(edit=tamper_c01, bench=MAIN)
        self.edit_answers(lambda cases: cases.pop("C01"))
        self.assertEqual(self.grade()[2], ["C01"])
        self.set_row("C01", {"pass": "1"})
        rows = self.grade()[0]
        self.assertTrue(rows["C01"].numbers)
        self.assertIs(grade.verdict(list(rows.values()))[0], False)

    def test_note_text_naming_the_metric_is_not_a_mismatch(self):
        self.ideal_run(bench=MAIN)
        self.set_row(
            "C02", {"pass": "0", "ghi_chu": "người rà nghi so_khop_cong_cu (xem lại)"}
        )
        verdict, lines = grade.verdict(list(self.grade()[0].values()))
        self.assertIs(verdict, True, lines)

    def test_complete_run_passes_and_stays_passing_on_regrade(self):
        self.ideal_run(bench=MAIN)
        for flags in ({}, {}, {"force": True}, {"force_human": True}):
            verdict, lines = grade.verdict(list(self.grade(**flags)[0].values()))
            self.assertIs(verdict, True, (flags, lines))

    def assert_undecided(self, rows, reason):
        verdict, lines = grade.verdict(list(rows.values()))
        self.assertIsNone(verdict, lines)
        self.assertIn("chưa kết luận", lines[0])
        self.assertIn(reason, "\n".join(lines))

    def test_run_missing_a_case_of_its_run_time_benchmark_is_undecided(self):
        self.ideal_run(MAIN[:9], bench=MAIN)
        self.assert_undecided(self.grade()[0], "thiếu 1 câu của bộ câu thử: C10")

    def test_graded_row_without_trace_is_undecided(self):
        self.ideal_run(bench=MAIN)
        self.set_row("C05", {"pass": "1", "ghi_chu": "người chấm tay"})
        self.drop_trace_of("C05")
        rows = self.grade()[0]
        self.assertIsNone(rows["C05"].numbers)
        self.assert_undecided(
            rows, "chưa kiểm được số (không có trace hoặc lỗi kỹ thuật): C05"
        )

    def test_error_row_is_undecided(self):
        def fail(rows):
            rows[4].update(error="RuntimeError: HTTP 429", output="")

        self.ideal_run(edit=fail, bench=MAIN)
        rows = self.grade()[0]
        self.assertEqual(rows["C05"]["pass"], "0")
        self.assertIsNone(rows["C05"].numbers)
        self.assert_undecided(rows, "lỗi kỹ thuật): C05")

    def test_try_run_graded_through_the_file_is_undecided(self):
        self.use("run-try")
        self.ideal_run(bench=MAIN)
        self.assert_undecided(self.grade()[0], "run-try không phải một lượt đánh giá")


def graded_rows(n=100, failed=(), refusals=10):
    """n dòng đã chấm và đã kiểm số; `refusals` dòng đầu là tu_choi; `failed` là số thứ tự (từ 0) bị trượt."""
    ids = tuple("R%03d" % i for i in range(n))
    rows = []
    for i, case_id in enumerate(ids):
        row = grade.Row(
            id=case_id,
            type="tu_choi" if i < refusals else "thuong",
            run_id="run-1@x",
            ghi_chu="",
        )
        row["pass"] = "0" if i in failed else "1"
        row.numbers, row.stem, row.bench = "", "run-1", ids
        rows.append(row)
    return rows


class TestVerdict(unittest.TestCase):
    def test_79_of_100_fails_and_80_of_100_passes(self):
        self.assertIs(grade.verdict(graded_rows(failed=range(79, 100)))[0], False)
        self.assertIs(grade.verdict(graded_rows(failed=range(80, 100)))[0], True)

    def test_one_failed_refusal_fails_even_at_99_percent(self):
        self.assertIs(grade.verdict(graded_rows(failed={99}))[0], True)
        self.assertIs(grade.verdict(graded_rows(failed={0}))[0], False)

    def test_one_number_mismatch_fails_even_when_every_row_passes(self):
        rows = graded_rows()
        rows[50].numbers = "số không có trong output công cụ: 1đ"
        self.assertIs(grade.verdict(rows)[0], False)

    def assert_undecided(self, rows):
        verdict, lines = grade.verdict(rows)
        self.assertIsNone(verdict, lines)
        self.assertIn("chưa kết luận", lines[0])

    def test_no_rows_is_undecided(self):
        self.assert_undecided([])

    def test_incomplete_runs_are_undecided(self):
        def blank(rows):
            rows[7]["pass"] = ""

        def junk(rows):
            rows[7]["pass"] = "x"

        def unchecked(rows):
            rows[7].numbers = None

        edits = {
            "thiếu một câu lúc chạy": lambda rows: rows.pop(),
            "câu chưa chấm": blank,
            "pass không phải 0/1": junk,
            "chưa kiểm số": unchecked,
        }
        for name, edit in edits.items():
            with self.subTest(name):
                rows = graded_rows()
                edit(rows)
                self.assert_undecided(rows)

    def test_run_without_a_refusal_row_is_undecided(self):
        self.assert_undecided(graded_rows(refusals=0))

    def test_files_that_are_not_runs_are_undecided_by_name_or_run_id(self):
        for name in ("run-try", "run-fake", "run-mock", "run-error", "run-stopped"):
            with self.subTest(name=name, by="tên file"):
                rows = graded_rows()
                for row in rows:
                    row.stem = name
                self.assert_undecided(rows)
            with self.subTest(name=name, by="run_id"):
                rows = graded_rows()
                rows[3]["run_id"] = name + "@abc"
                self.assert_undecided(rows)


class GuessingStub(ModelStub):
    """Như model lý tưởng, trừ một khoản không đủ căn cứ mỗi lần gán nhóm bị gán "mua_sam"."""

    guessed: list = []

    def __call__(self, system, user):
        reply = super().__call__(system, user)
        if system.startswith(agent.LABEL_TASK):
            unclear = {
                r["description"] for r in TRUTH.values() if r["category"] == "khong_ro"
            }
            item = next((i for i in json.loads(user) if i["mo_ta"] in unclear), None)
            if item:
                self.guessed.append(item["mo_ta"])
                reply = dict(
                    reply,
                    text=json.dumps(
                        dict(json.loads(reply["text"]), **{item["id"]: "mua_sam"})
                    ),
                )
        return reply


class TestGraderGuards(GraderCase):
    def test_guessing_a_group_for_an_unclear_transaction_fails(self):
        """Câu trả lời vẫn nói còn phần chưa rõ, nên chỉ chốt "đoán nhóm" mới bắt được."""
        case = oracle.cases()["C05"]
        self.assertIn("khong_doan_bua", case["metrics"])
        GuessingStub.guessed.clear()
        self.make_run({"C05": ideal_plan(case)}, stub=GuessingStub)
        self.assertTrue(
            GuessingStub.guessed, "không có khoản chưa rõ nào được gửi cho model"
        )
        self.assertRegex(self.row("C05")["output"], "(?i)(chưa|không) rõ")
        row = self.grade()[0]["C05"]
        self.assertEqual(row["pass"], "0")
        self.assertRegex(
            row["ghi_chu"],
            r"khong_doan_bua \(đoán nhóm cho khoản không đủ căn cứ: T\d{4}",
        )

    def test_money_in_an_answer_that_must_have_none_fails(self):
        for case_id in ("C06", "C26"):
            with self.subTest(case_id):
                case = oracle.cases(ALL)[case_id]
                self.assertTrue(case["no_money"])
                self.make_run({case_id: ideal_plan(case)})
                self.assertEqual(self.grade()[0][case_id]["pass"], "1")
                tampered = self.row(case_id)["output"] + "\nƯớc chừng 5.000.000đ."
                self.set_row(case_id, {"output": tampered, "pass": "", "ghi_chu": ""})
                row = self.grade()[0][case_id]
                self.assertEqual(row["pass"], "0")
                self.assertIn(
                    "dung_dap_an (có số tiền khi không được có)", row["ghi_chu"]
                )


class TestGraderCli(GraderCase):
    def run_main(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = grade.main(list(args))
        return code, out.getvalue()

    def test_bad_arguments_exit_2_without_writing(self):
        self.ideal_run(["C01"])
        before = read_bytes(self.path)
        bad = [
            [],
            [self.path, self.path],
            ["--force"],
            ["--force-humen"],
            ["--force-humen", self.path],
            [self.path, "--forse"],
        ]
        for args in bad:
            with self.subTest(args=args):
                self.assertEqual(self.run_main(*args)[0], 2)
                self.assert_untouched(before)

    def test_help_exits_0_and_names_force_human(self):
        for flag in ("-h", "--help"):
            code, out = self.run_main(flag)
            self.assertEqual(code, 0)
            self.assertIn("--force-human", out)

    def test_flags_reach_the_grader_and_output_says_what_happened(self):
        self.ideal_run(bench=MAIN)
        code, out = self.run_main(self.path)
        self.assertEqual(code, 0)
        self.assertIn("Đã điền pass / ghi_chu vào", out)
        self.assertIn("Kết luận §7: ĐẠT", out)
        self.set_row("C01", {"pass": "0", "ghi_chu": "người rà"})
        before = read_bytes(self.path)
        code, out = self.run_main(self.path, "--force")
        self.assertEqual(code, 0)
        self.assertIn("Không có gì thay đổi", out)
        self.assertIn("Giữ nguyên điểm người rà: C01", out)
        self.assert_untouched(before)
        code, out = self.run_main("--force-human", self.path)
        self.assertEqual(code, 0)
        self.assertEqual(self.row("C01")["pass"], "1")
        self.assertTrue(
            self.row("C01")["ghi_chu"].startswith("người rà | grade.py đạt [mã ")
        )


if __name__ == "__main__":
    unittest.main()
