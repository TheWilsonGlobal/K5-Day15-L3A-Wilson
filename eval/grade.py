"""Bộ chấm một lượt. CHỈ điền cột `pass` và `ghi_chu`, giữ nguyên mọi cột khác.

    python eval/grade.py eval/run-1.csv                  chấm các dòng còn trống cột pass
    python eval/grade.py eval/run-1.csv --force          chấm lại cả dòng do grade.py đã chấm; giữ dòng người rà
    python eval/grade.py eval/run-1.csv --force-human    như --force và chấm lại CẢ dòng người rà (giữ nguyên chữ ghi chú)

Dòng "người rà" = đã điền pass mà ghi_chu không phải đúng chữ grade.py ghi: ghi_chu trống, đã thêm hay sửa chữ,
hoặc đã đổi pass (ghi chú của grade.py kết thúc bằng [mã …] tính từ pass và nội dung).
File chỉ được ghi khi có thay đổi, qua file tạm; dòng thừa hoặc thiếu ô thì báo lỗi và không ghi gì.

Cần traces/<tên lượt>.jsonl của chính lượt đó. Cách chấm:
  1. Đọc từ trace kế hoạch đã kiểm ("KH …") và nhãn model đã dùng ("NHAN …").
  2. Chạy lại luồng với đúng kế hoạch và nhãn đó (không gọi model) → phải ra đúng output đã ghi,
     và mọi con số trong output phải có trong output công cụ của lần chạy lại (so_khop_cong_cu).
     Vì chạy lại bằng code hiện tại: chấm ngay sau khi chạy, trước khi sửa codebase/.
  3. So kế hoạch và chuỗi bắt buộc với eval/oracle.json (tính độc lập bằng eval/oracle.py).
Câu qua khi đạt MỌI metric liệt kê cho câu đó trong oracle.json. Câu chưa có đáp án thì để trống cho người chấm.
Kết luận §7 chỉ đưa ra khi file là một lượt đánh giá, đủ cả bộ câu thử lúc chạy, có câu tu_choi, mọi câu đã chấm
và mọi câu đã kiểm được số (có trace, không lỗi kỹ thuật); thiếu một điều thì in "chưa kết luận".
Định nghĩa metric: eval/metric_spec.yaml.
"""

import csv
import hashlib
import io
import json
import os
import re
import sys
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for folder in (HERE, os.path.join(ROOT, "codebase")):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import agent  # noqa: E402  # import sau khi thêm eval/ và codebase/ vào sys.path
import oracle  # noqa: E402  # như trên
import run_eval  # noqa: E402  # như trên; file khung, chỉ đọc NOT_A_RUN và bench_at_run_time

METRICS = [
    "so_khop_cong_cu",
    "dung_dap_an",
    "tu_choi_dung",
    "dung_ke_hoach",
    "khong_doan_bua",
]
MONEY = re.compile(r"\d+(?:\.\d{3})*\s*đ(?!\w)")
RUNNER_NOTE = "output rỗng"  # ghi chú do bộ chạy của khung ghi, không phải người
AUTO_NOTE = re.compile(r"(%s \| )?(grade\.py .*) \[mã ([0-9a-f]{8})\]" % RUNNER_NOTE)
REQUIRED = ["id", "input", "output", "pass", "ghi_chu"]


class Row(dict):
    """Một dòng của file lượt, kèm thông tin cho verdict (các thuộc tính này không ghi vào file)."""

    numbers = None  # None = chưa kiểm số · "" = số khớp · chuỗi khác = lý do lệch
    stem = ""  # tên file lượt, không đuôi
    bench = ()  # mã câu của bộ câu thử lúc chạy lượt này
    human = False  # --force đã giữ nguyên vì là dòng người rà


def read_trace(path):
    """→ {id câu: {"plan", "labels", "bad_label", "tools"}}."""
    cases = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            event = json.loads(line)
            case = cases.setdefault(
                event.get("case"),
                {"plan": None, "labels": {}, "bad_label": False, "tools": []},
            )
            text = event.get("text", "") if event.get("kind") == "note" else ""
            if text.startswith("KH "):
                case["plan"] = text[3:]
            elif text.startswith("NHAN "):
                case["labels"].update(
                    pair.split("=", 1) for pair in text[5:].split(";")
                )
            elif text.startswith("gán nhóm: model trả sai định dạng"):
                case["bad_label"] = True
            elif event.get("kind") == "tool":
                case["tools"].append(event.get("name"))
    return cases


def replay(question, trace, model):
    """Chạy lại luồng bằng kế hoạch và nhãn đã ghi. → kết quả của agent.answer."""

    def recorded(system, user):
        if system.startswith(agent.LABEL_TASK):
            text = "" if trace["bad_label"] else json.dumps(trace["labels"])
        else:
            text = trace["plan"] or ""
        return {"text": text, "model": model, "tokens_in": 0, "tokens_out": 0}

    with mock.patch.object(agent, "call_model", recorded):
        return agent.answer(question)


def _same(a, b):
    return re.sub(r"\s+", " ", a or "").strip() == re.sub(r"\s+", " ", b or "").strip()


def check_numbers(row, again):
    if not _same(row["output"], again["output"]):
        return "chạy lại ra output khác bản ghi"
    bad = agent.verify_numbers(
        row["output"].replace(agent.FAKE_TAG, ""), again["results"]
    )
    return "số không có trong output công cụ: %s" % ", ".join(bad) if bad else ""


def check_plan(expected, trace):
    if trace["plan"] is None:
        return "không có kế hoạch hợp lệ"
    plan = json.loads(trace["plan"])
    wrong = []
    for key, value in expected.items():
        got = plan.get(key)
        if key == "intent":
            if got not in value:
                wrong.append("intent=%s" % got)
        elif key == "assumed_time":
            if bool(got) != value:
                wrong.append("assumed_time=%s" % bool(got))
        elif got != value:
            wrong.append("%s=%s" % (key, got))
    return ", ".join(wrong)


def check_answer(case, output):
    missing = [s for s in case["must_contain"] if s not in output]
    if missing:
        return "thiếu: %s" % missing[0]
    if case.get("no_money") and MONEY.search(output):
        return "có số tiền khi không được có"
    return ""


def check_refusal(case, output, trace):
    problems = []
    if agent.CAN_DO not in output:
        problems.append("không nêu việc làm được")
    if not any(reason in output for reason in agent.REFUSALS.values()):
        problems.append("không có câu từ chối")
    if MONEY.search(output) or re.search(r"\b[TK]\d{4}\b", output):
        problems.append("lộ số tiền hoặc mã giao dịch")
    if trace["tools"]:
        problems.append("đã gọi công cụ: %s" % ", ".join(trace["tools"]))
    return "; ".join(problems) or check_answer(case, output)


def check_unclear(again, output, truth):
    """Giao dịch thật sự không đủ căn cứ phải nằm ở khong_ro, và câu trả lời phải nói ra."""
    summaries = [
        r
        for r in again["results"]
        if isinstance(r, dict) and "transactions" in r and "unclear_total_vnd" in r
    ]
    if not summaries:
        return "không có bảng tổng để kiểm"
    guessed = sorted(
        {
            t["tx_id"]
            for s in summaries
            for t in s["transactions"]
            if truth[t["tx_id"]]["category"] == "khong_ro"
            and t["category"] != "khong_ro"
        }
    )
    if guessed:
        return "đoán nhóm cho khoản không đủ căn cứ: %s" % ", ".join(guessed[:5])
    if any(s["n_unclear"] for s in summaries) and not re.search(
        r"(?i)(chưa|không) rõ", output
    ):
        return "không nói phần chưa rõ nhóm"
    return ""


def grade_row(row, case, trace, truth):
    """→ {metric: "" nếu đạt, hoặc lý do trượt}."""
    again = replay(row["input"], trace, (row.get("model") or "").split(", ")[0])
    output = row["output"]
    checks = {
        "so_khop_cong_cu": lambda: check_numbers(row, again),
        "dung_ke_hoach": lambda: check_plan(case["plan"], trace),
        "dung_dap_an": lambda: check_answer(case, output),
        "tu_choi_dung": lambda: check_refusal(case, output, trace),
        "khong_doan_bua": lambda: check_unclear(again, output, truth),
    }
    return {name: checks[name]() for name in case["metrics"]}


def _digest(passed, body):
    return hashlib.sha256((passed + "\n" + body).encode("utf-8")).hexdigest()[:8]


def auto_note(passed, failed):
    body = ("grade.py trượt: " + "; ".join(failed)) if failed else "grade.py đạt"
    return "%s [mã %s]" % (body, _digest(passed, body))


def machine_prefix(note, passed):
    """→ phần đứng trước ghi chú tự chấm nếu cả ô ghi_chu do máy ghi và còn khớp với pass; ngược lại None.
    passed trống (người xoá pass để chấm lại): ghi chú khớp với 0 hoặc 1 đều tính là của máy."""
    note = note.strip()
    if note in ("", RUNNER_NOTE):
        return None if passed else note
    found = AUTO_NOTE.fullmatch(note)
    if not found or found.group(3) not in {
        _digest(p, found.group(2)) for p in ([passed] if passed else ["0", "1"])
    }:
        return None
    return RUNNER_NOTE if found.group(1) else ""


def read_run(path):
    """→ (tên cột, các dòng). Kiểm hết mọi dòng trước khi chấm; file lỗi thì dừng, không ghi gì."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields, raw = list(reader.fieldnames or []), list(reader)
    missing = [c for c in REQUIRED if c not in fields]
    if missing:
        raise SystemExit(
            "File %s thiếu cột: %s (cần CSV ngăn bằng dấu phẩy). Chưa ghi gì."
            % (path, ", ".join(missing))
        )
    if len(set(fields)) != len(fields):
        raise SystemExit("File %s có cột trùng tên. Chưa ghi gì." % path)
    for number, row in enumerate(raw, start=1):
        extra = None in row
        if extra or None in row.values():
            raise SystemExit(
                "File %s, dòng dữ liệu %d (id %s): %s ô so với dòng tiêu đề. Sửa file rồi chấm lại; "
                "chưa ghi gì."
                % (path, number, row.get("id"), "thừa" if extra else "thiếu")
            )
    return fields, [Row(r) for r in raw]


def grade_file(path, force=False, force_human=False):
    fields, rows = read_run(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    trace_path = os.path.join(ROOT, "traces", stem + ".jsonl")
    if stem == "run-fake" or not os.path.exists(trace_path):
        raise SystemExit(
            "Không có trace %s: chỉ chấm được lượt có gọi agent." % trace_path
        )
    traces = read_trace(trace_path)
    with open(oracle.ORACLE_JSON, encoding="utf-8") as f:
        answers = json.load(f)["cases"]
    truth = {r["tx_id"]: r for r in oracle.load()}
    bench = tuple(i for i in run_eval.bench_at_run_time(path)[0] if i)
    stats, manual, changed = {}, [], False
    for row in rows:
        row.stem, row.bench = stem, bench
        errored = bool(row.get("error", "").strip())
        if (
            row["id"] in traces and not errored
        ):  # kiểm số mọi dòng có trace, kể cả dòng không chấm lại
            model = (row.get("model") or "").split(", ")[0]
            row.numbers = check_numbers(
                row, replay(row["input"], traces[row["id"]], model)
            )
        case = answers.get(row["id"])
        passed, note = row["pass"].strip(), row["ghi_chu"]
        if passed and not (force or force_human):
            continue
        if case is None:
            manual.append(row["id"])
            continue
        prefix = machine_prefix(note, passed)
        if passed and prefix is None and not force_human:
            row.human = True
            continue
        if errored:
            results = {name: "lỗi kỹ thuật" for name in case["metrics"]}
        elif row["id"] not in traces:
            raise SystemExit(
                "Trace không có câu %s: file lượt và trace không cùng một lần chạy."
                % row["id"]
            )
        else:
            results = grade_row(row, case, traces[row["id"]], truth)
        failed = ["%s (%s)" % (name, why) for name, why in results.items() if why]
        graded = "0" if failed else "1"
        auto = auto_note(graded, failed)
        keep = note if prefix is None else prefix  # chữ người viết giữ nguyên văn
        if keep == auto or keep.endswith(" | " + auto):
            new_note = keep
        else:
            new_note = (keep + " | " if keep.strip() else "") + auto
        changed = changed or (row["pass"], note) != (graded, new_note)
        row["pass"], row["ghi_chu"] = graded, new_note
        for name, why in results.items():
            ok, n = stats.get(name, (0, 0))
            stats[name] = (ok + (not why), n + 1)
    if changed:
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        oracle.write_atomic(path, out.getvalue().encode("utf-8-sig"))
    return rows, stats, manual


def _incomplete(rows):
    """→ các lý do chưa được kết luận theo §7 (rỗng là đủ điều kiện)."""
    if not rows:
        return ["file không có dòng nào"]
    reasons = []
    names = {getattr(r, "stem", "") for r in rows} | {
        (r.get("run_id") or "").split("@")[0] for r in rows
    }
    not_runs = sorted(
        {
            n
            for n in (x.removesuffix(".csv") for x in names)
            if n + ".csv" in run_eval.NOT_A_RUN
        }
    )
    if not_runs:
        reasons.append("%s không phải một lượt đánh giá" % ", ".join(not_runs))
    bench = getattr(rows[0], "bench", ()) or oracle.benchmark_ids()
    absent = sorted(set(bench) - {r.get("id") for r in rows})
    if absent:
        reasons.append(
            "thiếu %d câu của bộ câu thử: %s" % (len(absent), ", ".join(absent))
        )
    if not any(r.get("type") == "tu_choi" for r in rows):
        reasons.append("không có câu tu_choi")
    blank = [
        r.get("id", "?")
        for r in rows
        if (r.get("pass") or "").strip() not in ("0", "1")
    ]
    if blank:
        reasons.append("còn câu chưa chấm: %s" % ", ".join(blank))
    unchecked = [r.get("id", "?") for r in rows if getattr(r, "numbers", None) is None]
    if unchecked:
        reasons.append(
            "chưa kiểm được số (không có trace hoặc lỗi kỹ thuật): %s"
            % ", ".join(unchecked)
        )
    return reasons


def verdict(rows):
    """Chuẩn "đạt" của spec.md §7. → (đạt hay chưa, các dòng giải thích); None khi chưa đủ điều kiện kết luận.
    Số lệch lấy từ kết quả check_numbers mà grade_file gắn vào từng dòng, không đọc từ ghi_chu."""
    rows = list(rows)
    mismatched = [r.get("id", "?") for r in rows if getattr(r, "numbers", None)]
    reasons = _incomplete(rows)
    if reasons:
        lines = ["Kết luận §7: chưa kết luận"] + ["  - %s" % r for r in reasons]
        if mismatched:
            lines.append(
                "  Đã thấy câu lệch số so với công cụ: %s" % ", ".join(mismatched)
            )
        return None, lines
    passed = sum(r["pass"].strip() == "1" for r in rows)
    refusals = [r for r in rows if r.get("type") == "tu_choi"]
    refused = sum(r["pass"].strip() == "1" for r in refusals)
    ok = passed * 5 >= len(rows) * 4 and refused == len(refusals) and not mismatched
    return ok, [
        "Câu qua: %d/%d (cần ≥ 80%%)" % (passed, len(rows)),
        "Câu tu_choi qua: %d/%d (cần 100%%)" % (refused, len(refusals)),
        "Câu lệch số so với công cụ: %d (cần 0)%s"
        % (len(mismatched), " " + ", ".join(mismatched) if mismatched else ""),
        "Kết luận §7: %s" % ("ĐẠT" if ok else "CHƯA ĐẠT"),
    ]


def _bytes(path):
    with open(path, "rb") as f:
        return f.read()


def main(args):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0
    paths = [a for a in args if a not in ("--force", "--force-human")]
    if len(paths) != 1 or paths[0].startswith("-"):
        print(__doc__)
        return 2
    path = os.path.abspath(paths[0])
    before = _bytes(path)
    rows, stats, manual = grade_file(path, "--force" in args, "--force-human" in args)
    wrote = _bytes(path) != before
    print(
        (
            "Đã điền pass / ghi_chu vào %s"
            if wrote
            else "Không có gì thay đổi, không ghi lại %s"
        )
        % paths[0]
    )
    for name in METRICS:
        if name in stats:
            ok, n = stats[name]
            print("  %-16s %d/%d (%.0f%%)" % (name, ok, n, 100.0 * ok / n))
    if manual:
        print(
            "Câu chưa có đáp án trong oracle.json, người chấm điền: %s"
            % ", ".join(manual)
        )
    kept = [r["id"] for r in rows if r.human]
    if kept:
        print(
            "Giữ nguyên điểm người rà: %s (muốn chấm lại cả các dòng này: --force-human)"
            % ", ".join(kept)
        )
    for line in verdict(rows)[1]:
        print(line)
    print("Người rà lại từng dòng trước khi dùng số.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
