#!/usr/bin/env python3
"""真题导入脚本：把 data/realexam/{exam}.json 里的真题入库(带溯源)。

会做三件事：
1. 逐条入库（is_real=1，连同 exam_year/paper/q_no/points 溯源列）；
2. 登记 realexam_imports（批次对账）；
3. 溯源完整性校验：缺 年份/题号/分值 的记录列出，保证不漏标。

用法：
  python scripts/import_realexam.py                 # 导入全部考试
  python scripts/import_realexam.py --exam ap_physics_1 --year-from 2010
  python scripts/import_realexam.py --check         # 仅校验不落库
"""
from __future__ import annotations
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import Database  # noqa: E402
from src.services.paper_builder import REALEXAM_DIR, EXAM_FILES  # noqa: E402


def _year(key):  # key 'ap_physics_1' 无年份标记时由外部文件承载，这里保留接口
    return key


def load_real(exam):
    path = os.path.join(REALEXAM_DIR, f"{exam}.json")
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for q in data:
        q.setdefault('is_real', 1)
        q['exam_type'] = exam
    return data


def main():
    ap = argparse.ArgumentParser(description="真题导入 + 溯源校验")
    ap.add_argument("--exam", default=None, help="考试类型，默认全部")
    ap.add_argument("--year-from", type=int, default=None)
    ap.add_argument("--year-to", type=int, default=None)
    ap.add_argument("--check", action="store_true", help="仅校验溯源不落库")
    args = ap.parse_args()

    db = Database()
    exams = [args.exam] if args.exam else list(EXAM_FILES.keys())
    report = {}
    for exam in exams:
        real = load_real(exam)
        incomplete = []
        for q in real:
            if q.get('exam_year') is None or q.get('q_no') is None \
                    or q.get('points') is None:
                incomplete.append({
                    "external_id": q.get('external_id'),
                    "缺": [k for k in ('exam_year', 'q_no', 'points')
                           if q.get(k) is None],
                })
        if args.check:
            report[exam] = {"total": len(real),
                            "incomplete_src": incomplete,
                            "message": "仅校验模式，未落库"}
            continue
        new = db.save_questions(real)
        db.log_realexam_import(exam, batch=f"{exam}-realexam",
                               year_from=args.year_from,
                               year_to=args.year_to,
                               count=new, status="success",
                               message=f"新增{new}/共{len(real)}，缺标{len(incomplete)}")
        report[exam] = {"source_total": len(real), "new": new,
                        "incomplete_src": incomplete}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
