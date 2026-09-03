#!/usr/bin/env python3
"""一键导出三种可下载产物（题目only / 答案only / 题目+答案）。

用法：
  python scripts/export_papers.py [--exam ap_physics_1] [--outdir data/download]
  # 不传 --exam 时导出全部考试
"""
from __future__ import annotations
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import Database  # noqa: E402
from src.services.paper_export import export_exam, export_all  # noqa: E402
from src.organization.kp_catalog import KnowledgePointCatalog  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="导出三种下载产物")
    ap.add_argument("--exam", default=None, help="考试类型，默认全部")
    ap.add_argument("--outdir", default=None, help="输出目录，默认 data/download")
    args = ap.parse_args()

    catalog = KnowledgePointCatalog()
    db = Database()
    if args.exam:
        res = export_exam(args.exam, catalog, db=db,
                          outdir=args.outdir or "data/download")
        print("导出完成:", res)
    else:
        res = export_all(db=db)
        print("导出完成:", res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
