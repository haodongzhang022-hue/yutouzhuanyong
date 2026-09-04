#!/usr/bin/env python3
"""真题 no-miss 对账：比对"历年应有真题清单"与题库实际已入真题。

报告每类考试历年逐卷的 齐/缺。missing 为空 = 该考试真题全量不缺。

用法：
  python scripts/check_realexam.py                       # 对账全部考试
  python scripts/check_realexam.py --exam ap_physics_1   # 仅对账指定考试
  python scripts/check_realexam.py --json                # 输出 JSON
"""
from __future__ import annotations
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import Database  # noqa: E402
from src.services import realexam_manifest as rm  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="真题 no-miss 对账")
    ap.add_argument("--exam", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    db = Database()
    manifest = rm._load_manifest()
    exams = manifest.get("exams", {})
    targets = [args.exam] if args.exam else list(exams.keys())

    coverage_by_exam = {}
    for exam in targets:
        coverage_by_exam[exam] = db.realexam_paper_coverage(exam)

    if args.exam:
        result = rm.audit_realexam(args.exam,
                                   coverage_by_exam[args.exam])
    else:
        result = rm.audit_all(coverage_by_exam)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # 人类可读报告
    if "audited" in result and isinstance(result["audited"], dict):
        rows = result["audited"]
    else:
        rows = {result["exam"]: result}
    lines = ["真题 no-miss 对账报告", "=" * 40]
    for exam, r in rows.items():
        if not r.get("audited"):
            lines += ["", f"[{exam}] {r.get('message','')}"]
            continue
        lines += ["", f"## {r.get('display', exam)}（{exam}）",
                  f" 开考年起：{r.get('start_year')}｜覆盖至：{r.get('current_year')}"
                  f"｜应含卷数：{r.get('expected_total')}"
                  f"｜已入：{r.get('present_total')}"
                  f"｜缺：{r.get('missing_count')}"]
        if r.get("note"):
            lines += [f"  注：{r['note']}"]
        if r.get("missing"):
            lines += ["  缺失（待补）："]
            for y, p in r["missing"]:
                lines += [f"    - {y} · {p or '(未标卷)'}"]
        if r.get("extra"):
            lines += ["  清单外（库中多出/需人工核对是否扩清单）："]
            for y, p in r["extra"]:
                lines += [f"    - {y} · {p or '(未标卷)'}"]
        if r.get("blank_paper_records"):
            lines += [f"  提示：有 {r['blank_paper_records']} 条真题未填『卷』字段，"
                      "无法归卷，请补齐 paper。" ]
        lines += ["  " + ("✅ 该考试真题全量齐全、无遗漏。" if r.get("complete")
                          else "⚠️ 存在缺口，见上方明细。")]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
