"""真题 no-miss 对账引擎。

依据 data/realexam/manifest.yaml 里的"历年应有试卷清单"，比对题库中已入的
真题记录，逐考试/逐年/逐卷报告：
  - expected     应含的试卷组合（year × paper）
  - present      已入库的
  - missing      缺失的（= 该补的真题卷）
  - extra        清单外多出的记录（供人工确认是否要扩清单）

由此保证用户强调的"真题一个不漏"：对账后 missing=[] 即为全量齐全。
仅做结构对账，不新增题目内容；真实真题原文需经授权渠道(见 README)持续投喂。
"""
from __future__ import annotations
import json
import os
from datetime import date
from typing import Dict, List, Optional

from src.paths import PROJECT_ROOT

MANIFEST_PATH = os.path.join(PROJECT_ROOT, "data", "realexam", "manifest.yaml")


def _load_manifest(path: str = MANIFEST_PATH) -> Dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"真题清单不存在: {path}")
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def expected_papers(exam_cfg: Dict, current_year: int) -> List[tuple]:
    """按清单展开应含的 (year, paper) 组合（含题解口径说明）。"""
    start = exam_cfg.get("start_year", 2010)
    papers = exam_cfg.get("papers", ["单卷"]) or ["单卷"]
    years = list(range(start, current_year + 1))
    out = []
    for y in years:
        for p in papers:
            out.append((y, p))
    return out


def audit_realexam(exam_type: str, coverage: Dict[tuple, Dict],
                   current_year: Optional[int] = None,
                   path: str = MANIFEST_PATH) -> Dict:
    """对账：coverage 来自 db.realexam_paper_coverage(exam_type)。"""
    manifest = _load_manifest(path)
    exams = manifest.get("exams", {})
    cfg = exams.get(exam_type)
    if cfg is None:
        return {"exam": exam_type, "audited": False,
                "message": f"清单未登记考试 {exam_type}，跳过对账"}
    cur = current_year or date.today().year
    expected = expected_papers(cfg, cur)
    present_set = set(coverage.keys())
    expected_set = set(expected)

    missing = sorted(expected_set - present_set)
    present = sorted(expected_set & present_set)
    # 库中有但不在清单期望内的组合
    extra = sorted(present_set - expected_set)

    # 空 paper 字段的真题（缺"卷"标识）→ 无法归到某卷，按 gap 提示
    n_blank_paper = sum(
        1 for (y, p), v in coverage.items() if not p)

    return {
        "exam": exam_type,
        "display": cfg.get("display", exam_type),
        "audited": True,
        "start_year": cfg.get("start_year"),
        "current_year": cur,
        "papers_per_year": cfg.get("papers", []),
        "expected_total": len(expected),
        "present_total": len(present),
        "present": present,
        "missing": missing,
        "missing_count": len(missing),
        "extra": extra,
        "blank_paper_records": n_blank_paper,
        "complete": (len(missing) == 0 and n_blank_paper == 0),
        "note": cfg.get("note", ""),
    }


def audit_all(coverage_by_exam: Dict[str, Dict[tuple, Dict]],
              current_year: Optional[int] = None,
              path: str = MANIFEST_PATH) -> Dict:
    manifest = _load_manifest(path)
    exams = manifest.get("exams", {})
    results = {}
    for exam_type in exams:
        results[exam_type] = audit_realexam(
            exam_type, coverage_by_exam.get(exam_type, {}),
            current_year=current_year, path=path)
    return {"audited": results}
