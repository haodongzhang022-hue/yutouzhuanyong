#!/usr/bin/env python3
"""真题：持续同步 + no-miss 对账 一键脚本。

把 data/realexam/{exam}.json 里新增真题幂等入库并重建专项卷，
随后按清单对账，报告哪些年份/卷还缺（保证"真题一个不漏"）。

用法：
  python scripts/realexam_sync_check.py                 # 全部考试
  python scripts/realexam_sync_check.py --exam ap_physics_1
"""
from __future__ import annotations
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import Database  # noqa: E402
from src.services import realexam_manifest as rm  # noqa: E402
from src.services.realexam_sync import sync_all, sync_realexam  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="真题同步 + no-miss 对账")
    ap.add_argument("--exam", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    db = Database()
    if args.exam:
        sync_report = sync_realexam(args.exam, db=db)
        exams = [args.exam]
    else:
        sync_report = sync_all(db=db)
        exams = list(sync_report["synced"].keys())

    coverage = {e: db.realexam_paper_coverage(e) for e in exams}
    if args.exam:
        audit = rm.audit_realexam(args.exam, coverage[args.exam])
    else:
        audit = rm.audit_all(coverage)

    if args.json:
        print(json.dumps({"sync": sync_report, "audit": audit},
                         ensure_ascii=False, indent=2))
        return 0
    print("== 同步 ==")
    for e, r in (sync_report["synced"].items() if "synced" in sync_report
                 else [(args.exam, sync_report)]):
        print(f"[{e}] 源 {r['source_total']} 条 / 新增 {r['new']} 条"
              f" / 缺标 {len(r['incomplete_src'])}")
    print("\n== no-miss 对账 ==")
    rows = (audit["audited"] if ("audited" in audit
            and isinstance(audit["audited"], dict))
            else {audit["exam"]: audit})
    for e, r in rows.items():
        tag = "✅齐全" if r.get("complete") else "⚠️有缺"
        print(f"[{e}] {tag} 应含 {r.get('expected_total')} 卷组，"
              f"已入 {r.get('present_total')}，缺 {r.get('missing_count')}")
        for y, p in r.get("missing", []):
            print(f"   缺: {y} · {p or '(未标卷)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
