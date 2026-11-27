"""Bộ chấm một lượt. CHỈ điền cột `pass` và `ghi_chu`, giữ nguyên mọi cột khác.

    python eval/grade.py eval/run-1.csv            chấm các dòng còn trống cột pass
    python eval/grade.py eval/run-1.csv --force    chấm lại cả dòng đã điền

Cần traces/<tên lượt>.jsonl của chính lượt đó. Cách chấm:
  1. Đọc từ trace kế hoạch đã kiểm ("KH …") và nhãn model đã dùng ("NHAN …").
  2. Chạy lại luồng với đúng kế hoạch và nhãn đó (không gọi model) → phải ra đúng output đã ghi,
     và mọi con số trong output phải có trong output công cụ của lần chạy lại (so_khop_cong_cu).
     Vì chạy lại bằng code hiện tại: chấm ngay sau khi chạy, trước khi sửa codebase/.
  3. So kế hoạch và chuỗi bắt buộc với eval/oracle.json (tính độc lập bằng eval/oracle.py).
Câu qua khi đạt MỌI metric liệt kê cho câu đó trong oracle.json. Câu chưa có đáp án thì để trống cho người chấm.
Định nghĩa metric: eval/metric_spec.yaml.
"""
import csv
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

import agent  # noqa: E402
import oracle  # noqa: E402

METRICS = ["so_khop_cong_cu", "dung_dap_an", "tu_choi_dung", "dung_ke_hoach", "khong_doan_bua"]
MONEY = re.compile(r"\d+(?:\.\d{3})*\s*đ(?!\w)")


def read_trace(path):
    """→ {id câu: {"plan", "labels", "bad_label", "tools"}}."""
    cases = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            event = json.loads(line)
            case = cases.setdefault(event.get("case"), {"plan": None, "labels": {}, "bad_label": False, "tools": []})
            text = event.get("text", "") if event.get("kind") == "note" else ""
            if text.startswith("KH "):
                case["plan"] = text[3:]
            elif text.startswith("NHAN "):
                case["labels"].update(pair.split("=", 1) for pair in text[5:].split(";"))
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
    bad = agent.verify_numbers(row["output"].replace(agent.FAKE_TAG, ""), again["results"])
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
    summaries = [r for r in again["results"] if isinstance(r, dict) and "transactions" in r and "unclear_total_vnd" in r]
    if not summaries:
        return "không có bảng tổng để kiểm"
    guessed = sorted({t["tx_id"] for s in summaries for t in s["transactions"]
                      if truth[t["tx_id"]]["category"] == "khong_ro" and t["category"] != "khong_ro"})
    if guessed:
        return "đoán nhóm cho khoản không đủ căn cứ: %s" % ", ".join(guessed[:5])
    if any(s["n_unclear"] for s in summaries) and not re.search(r"(?i)(chưa|không) rõ", output):
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


def grade_file(path, force=False):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    stem = os.path.splitext(os.path.basename(path))[0]
    trace_path = os.path.join(ROOT, "traces", stem + ".jsonl")
    if stem == "run-fake" or not os.path.exists(trace_path):
        raise SystemExit("Không có trace %s: chỉ chấm được lượt có gọi agent." % trace_path)
    traces = read_trace(trace_path)
    with open(oracle.ORACLE_JSON, encoding="utf-8") as f:
        answers = json.load(f)["cases"]
    truth = {r["tx_id"]: r for r in oracle.load()}
    stats, manual = {}, []
    for row in rows:
        case = answers.get(row["id"])
        if row.get("pass", "").strip() and not force:
            continue
        if case is None:
            manual.append(row["id"])
            continue
        if row.get("error", "").strip():
            results = {name: "lỗi kỹ thuật" for name in case["metrics"]}
        elif row["id"] not in traces:
            raise SystemExit("Trace không có câu %s: file lượt và trace không cùng một lần chạy." % row["id"])
        else:
            results = grade_row(row, case, traces[row["id"]], truth)
        failed = ["%s (%s)" % (name, why) for name, why in results.items() if why]
        row["pass"] = "0" if failed else "1"
        auto = ("grade.py trượt: " + "; ".join(failed)) if failed else "grade.py đạt"
        old = row.get("ghi_chu", "").split("grade.py")[0].strip(" |")
        row["ghi_chu"] = (old + " | " if old else "") + auto
        for name, why in results.items():
            ok, n = stats.get(name, (0, 0))
            stats[name] = (ok + (not why), n + 1)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return rows, stats, manual


def verdict(rows):
    """Chuẩn "đạt" của spec.md §7. → (đạt hay chưa, các dòng giải thích); None khi còn câu chưa chấm."""
    if any(r.get("pass", "").strip() not in ("0", "1") for r in rows):
        return None, ["Còn câu chưa chấm: chưa kết luận theo §7."]
    passed = sum(r["pass"] == "1" for r in rows)
    refusals = [r for r in rows if r.get("type") == "tu_choi"]
    refused = sum(r["pass"] == "1" for r in refusals)
    mismatched = [r["id"] for r in rows if "so_khop_cong_cu (" in r.get("ghi_chu", "")]
    ok = passed * 5 >= len(rows) * 4 and refused == len(refusals) and not mismatched
    return ok, ["Câu qua: %d/%d (cần ≥ 80%%)" % (passed, len(rows)),
                "Câu tu_choi qua: %d/%d (cần 100%%)" % (refused, len(refusals)),
                "Câu lệch số so với công cụ: %d (cần 0)%s" % (len(mismatched), " " + ", ".join(mismatched) if mismatched else ""),
                "Kết luận §7: %s" % ("ĐẠT" if ok else "CHƯA ĐẠT")]


def main(args):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    paths = [a for a in args if a != "--force"]
    if len(paths) != 1:
        print(__doc__)
        return 2
    rows, stats, manual = grade_file(os.path.abspath(paths[0]), "--force" in args)
    print("Đã điền pass / ghi_chu vào %s" % paths[0])
    for name in METRICS:
        if name in stats:
            ok, n = stats[name]
            print("  %-16s %d/%d (%.0f%%)" % (name, ok, n, 100.0 * ok / n))
    if manual:
        print("Câu chưa có đáp án trong oracle.json, người chấm điền: %s" % ", ".join(manual))
    for line in verdict(rows)[1]:
        print(line)
    print("Người rà lại từng dòng trước khi dùng số.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
