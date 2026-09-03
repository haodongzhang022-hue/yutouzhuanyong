#!/usr/bin/env python3
"""一键组织题库：平铺 JSON -> 知识点专项练习卷 + AI 索引 + 目录 + 卷登记。

用法：
    python scripts/organize_bank.py                        # 全部题库
    python scripts/organize_bank.py --exam ap_physics_1    # 指定考试
    python scripts/organize_bank.py --outdir data/papers   # 指定输出
组织逻辑集中在 src/services/paper_builder.py，本脚本是 CLI 入口。
"""
from __future__ import annotations
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.paths import DATA_DIR                      # noqa: E402
from src.services.paper_builder import (           # noqa: E402
    rebuild_papers, EXAM_FILES,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exam", default=None,
                    help="exam: ap_physics_1 / physics_bowl_d1（默认全部）")
    ap.add_argument("--outdir",
                    default=os.path.join(DATA_DIR, "papers"))
    args = ap.parse_args()
    exams = [args.exam] if args.exam else list(EXAM_FILES.keys())
    from src.services.paper_builder import organize_exam
    from src.organization.kp_catalog import KnowledgePointCatalog
    catalog = KnowledgePointCatalog()
    total = 0
    for exam in exams:
        res = organize_exam(exam, catalog, outdir=args.outdir)
        total += res["papers"]
        print(f"[organize] {exam}: {res['papers']} 份卷 / {res['questions']} 题")
    print(f"完成。共 {total} 份专项卷已输出到: {os.path.abspath(args.outdir)}")


if __name__ == "__main__":
    main()
