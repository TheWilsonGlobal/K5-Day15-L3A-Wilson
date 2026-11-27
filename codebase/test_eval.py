"""Test bộ câu thử, đáp án và bộ chấm. Model được thay bằng câu trả lời dựng sẵn; file tạm, không đụng eval/.

    python -m unittest discover -s codebase -p "test_*.py"
"""
import csv
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for folder in (HERE, os.path.join(ROOT, "eval")):
    if folder not in sys.path:
        sys.path.insert(0, folder)
os.environ["MODEL_PROVIDER"] = "fake"

import add_cases  # noqa: E402
import agent  # noqa: E402
import grade  # noqa: E402
import oracle  # noqa: E402
import run_eval  # noqa: E402
import tracing  # noqa: E402
from test_tools import ModelStub  # noqa: E402

with open(os.path.join(ROOT, "eval", "benchmark.csv"), encoding="utf-8-sig", newline="") as f:
    BENCH = {r["id"]: r for r in csv.DictReader(f)}
with open(add_cases.DRAFT, encoding="utf-8-sig", newline="") as f:
    DRAFT = {r["id"]: r for r in csv.DictReader(f)}
ALL = dict(DRAFT, **BENCH)   # câu đã trong bộ + câu soạn sẵn


def ideal_plan(case):
    """Kế hoạch mà một model hiểu đúng câu hỏi sẽ trả."""
    plan = dict(case["plan"], intent=case["plan"]["intent"][0])
    if plan["intent"] == "noi_ban":   # đáp án không so tên nơi bán nguyên văn, nhưng kế hoạch phải có
        plan["merchant"] = "cơm cô ba"
    if plan["intent"] == "tu_choi":
        words = case["must_contain"][0] if case["must_contain"] else "không tư vấn đầu tư"
        plan["reason"] = next(k for k, v in agent.REFUSALS.items() if words in v)
    return plan


class TestBenchmark(unittest.TestCase):
    def test_oracle_json_is_current_and_matches_benchmark_ids(self):
        with open(oracle.ORACLE_JSON, encoding="utf-8") as f:
            saved = json.load(f)["cases"]
        self.assertEqual(saved, json.loads(json.dumps(oracle.cases())))
        self.assertTrue(set(saved) <= set(BENCH))

    def test_inputs_are_not_hardcoded_in_prompts(self):
        for name in ("agent.py", "ai.py", "tools.py"):
            with open(os.path.join(HERE, name), encoding="utf-8") as f:
                code = f.read()
            for row in BENCH.values():
                self.assertNotIn(row["input"], code, (name, row["id"]))

    def test_types(self):
        self.assertTrue({r["type"] for r in BENCH.values()} == {"thuong", "kho", "tu_choi"})
        for case_id, case in oracle.cases(ALL).items():
            self.assertEqual("tu_choi_dung" in case["metrics"], ALL[case_id]["type"] == "tu_choi", case_id)

    def test_every_draft_case_has_an_answer_and_review_source_exists(self):
        self.assertEqual(set(oracle.draft_cases()), set(DRAFT))
        with open(os.path.join(ROOT, "evidence", "reviews.csv"), encoding="utf-8-sig", newline="") as f:
            reviews = {r["ma"] for r in csv.DictReader(f)}
        for row in DRAFT.values():
            if row["source"].startswith("data_that"):
                self.assertIn(row["source"].split()[-1], reviews, row["id"])


class TestAddCases(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        self.bench, self.draft = os.path.join(tmp, "bench.csv"), os.path.join(tmp, "draft.csv")
        head = "id,input,expected,pass_criterion,type,source\r\n"
        with open(self.bench, "w", encoding="utf-8-sig", newline="") as f:
            f.write(head + "C01,a,e,p,kho,tu_viet\r\n")
        with open(self.draft, "w", encoding="utf-8-sig", newline="") as f:
            f.write(head + 'C11,"b, c",e,p,kho,data_that: review 1\r\nC12,d,e,p,kho,tu_viet\r\n'
                    + 'C13,g,e,p,kho,tu_viet\r\nC14,h,e,p,kho,tu_viet\r\n')

    def read(self):
        with open(self.bench, "rb") as f:
            return f.read()

    def test_appends_and_keeps_old_bytes(self):
        before = self.read()
        self.assertEqual(add_cases.add(["C11"], self.bench, self.draft), (2, 1))
        self.assertTrue(self.read().startswith(before))
        self.assertEqual([r["input"] for r in add_cases.read(self.bench)[1]], ["a", "b, c"])

    def test_rejects_bad_requests_without_writing(self):
        before = self.read()
        for ids in ([], ["C99"], ["C12"], ["C11", "C11"], ["C11", "C12", "C13"]):
            with self.assertRaises(ValueError):
                add_cases.add(ids, self.bench, self.draft)
        self.assertEqual(self.read(), before)
        add_cases.add(["C11"], self.bench, self.draft)
        with self.assertRaises(ValueError):
            add_cases.add(["C11"], self.bench, self.draft)


class TestGrader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        os.makedirs(os.path.join(self.tmp, "traces"))
        self.path = os.path.join(self.tmp, "run-9.csv")

    def make_run(self, plans, edit=None):
        """Chạy các câu qua đúng bộ chạy của khung, ghi file lượt và trace vào thư mục tạm."""
        rows, events = [], []
        for case_id, plan in plans.items():
            with mock.patch.object(agent, "call_model", tracing.model_call(ModelStub(plan).__call__)):
                row, trace = run_eval.call_case(agent.answer, tracing, case_id, ALL[case_id]["input"])
            self.assertEqual(row["error"], "")
            row.update({k: ALL[case_id][k] for k in ("id", "type", "input", "expected", "pass_criterion")})
            row.update({"run_id": "run-9@test", "pass": "", "ghi_chu": ""})
            rows.append(row)
            events += [dict(e, case=case_id) for e in trace]
        if edit:
            edit(rows)
        run_eval.write_csv(self.path, run_eval.OUT_COLS, rows)
        with open(os.path.join(self.tmp, "traces", "run-9.jsonl"), "w", encoding="utf-8") as f:
            f.writelines(json.dumps(e, ensure_ascii=False, default=str) + "\n" for e in events)

    def grade(self):
        answers = os.path.join(self.tmp, "oracle.json")
        with mock.patch.object(oracle, "benchmark_ids", lambda: set(ALL)):
            oracle.write_json(answers)
        with mock.patch.object(grade, "ROOT", self.tmp), mock.patch.object(oracle, "ORACLE_JSON", answers):
            rows, stats, manual = grade.grade_file(self.path)
        return {r["id"]: r for r in rows}, stats, manual

    def test_ideal_model_passes_every_case_and_other_columns_are_kept(self):
        self.make_run({i: ideal_plan(c) for i, c in oracle.cases(ALL).items()})
        with open(self.path, encoding="utf-8-sig", newline="") as f:
            before = list(csv.DictReader(f))
        rows, _, manual = self.grade()
        self.assertEqual({i: r["ghi_chu"] for i, r in rows.items() if r["pass"] != "1"}, {})
        self.assertEqual(manual, [])
        for old in before:
            keep = [k for k in old if k not in ("pass", "ghi_chu")]
            self.assertEqual([rows[old["id"]][k] for k in keep], [old[k] for k in keep])
        self.assertTrue(grade.verdict(list(rows.values()))[0])

    def test_wrong_period_fails_plan_and_answer_but_not_numbers(self):
        plan = dict(ideal_plan(oracle.cases()["C01"]), **{"from": "2026-09-01", "to": "2026-09-30"})
        self.make_run({"C01": plan})
        note = self.grade()[0]["C01"]["ghi_chu"]
        self.assertIn("dung_ke_hoach (", note)
        self.assertIn("dung_dap_an (", note)
        self.assertNotIn("so_khop_cong_cu (", note)

    def test_edited_number_fails_number_match(self):
        self.make_run({"C01": ideal_plan(oracle.cases()["C01"])},
                      edit=lambda rows: rows[0].update(output=rows[0]["output"].replace("39.061.000đ", "39.062.000đ")))
        rows = self.grade()[0]
        self.assertIn("so_khop_cong_cu (", rows["C01"]["ghi_chu"])
        self.assertFalse(grade.verdict(list(rows.values()))[0])

    def test_answering_a_forbidden_request_fails(self):
        self.make_run({"C09": {"intent": "liet_ke", "from": "2026-11-01", "to": "2026-11-27"}})
        row = self.grade()[0]["C09"]
        self.assertEqual(row["pass"], "0")
        self.assertIn("đã gọi công cụ", row["ghi_chu"])

    def test_filled_pass_is_not_overwritten(self):
        self.make_run({"C03": ideal_plan(oracle.cases()["C03"])},
                      edit=lambda rows: rows[0].update({"pass": "0", "ghi_chu": "người chấm"}))
        row = self.grade()[0]["C03"]
        self.assertEqual((row["pass"], row["ghi_chu"]), ("0", "người chấm"))


if __name__ == "__main__":
    unittest.main()
