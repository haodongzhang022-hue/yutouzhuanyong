"""真题持续同步服务（continuous acquisition）。

用户要求：真题一个不漏，且"持续获取到同类型题也录入"。本服务把
data/realexam/{exam}.json 作为**可持续投喂入口**：
  - 外部/授权源把新增真题(带完整溯源)按格式追加写入对应 json；
  - sync() 幂等入库(按 external_id 去重) → 登记 realexam_imports 批次 →
    触发受影响考试专项卷重建 → 返回增量报告。
  - 配合 scripts/check_realexam.py 的 no-miss 对账，可保证"全量、不漏"。

真实题目原文版权属于出题机构(College Board / AAPT)，须经官方公布或授权转写
渠道投喂（见 data/realexam/README.md），本服务不自造内容，只做幂等摄入与对账。
"""
from __future__ import annotations
import json
import logging
import os
from datetime import date
from typing import Dict, List, Optional

from src.models.database import Database
from src.services.paper_builder import REALEXAM_DIR, REALEXAM_FILES

logger = logging.getLogger(__name__)


def load_realexam_json(exam: str) -> List[Dict]:
    path = REALEXAM_FILES.get(exam)
    if not path or not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for q in data:
        q = dict(q)
        q.setdefault("is_real", 1)
        q.setdefault("exam_type", exam)
        out.append(q)
    return out


def sync_realexam(exam: str, db: Optional[Database] = None,
                  rebuild: bool = True) -> Dict:
    """把 data/realexam/{exam}.json 全量幂等同步入库并触发重建。"""
    db = db or Database()
    real = load_realexam_json(exam)
    incomplete = []
    for q in real:
        if q.get("exam_year") is None or q.get("q_no") is None \
                or q.get("points") is None:
            incomplete.append({
                "external_id": q.get("external_id"),
                "缺": [k for k in ("exam_year", "q_no", "points")
                       if q.get(k) is None],
            })
    new = db.save_questions(real)
    db.log_realexam_import(
        exam, batch=f"{exam}-realexam-sync", count=new,
        status="success",
        message=f"同步源{len(real)}条，新增{new}，缺标{len(incomplete)}")
    rebuilt = None
    if rebuild and new > 0:
        try:
            from src.organization.kp_catalog import KnowledgePointCatalog
            from src.services.paper_builder import organize_exam
            rebuilt = organize_exam(exam, KnowledgePointCatalog(),
                                    db=db, trigger="realexam_sync",
                                    version="realexam-auto")
        except Exception as e:  # noqa: BLE001
            logger.warning("真题同步后重建失败 [%s]: %s", exam, e)
            rebuilt = {"error": str(e)}
    return {"exam": exam, "source_total": len(real), "new": new,
            "incomplete_src": incomplete, "rebuilt": rebuilt}


def sync_all(db: Optional[Database] = None,
             exams: Optional[List[str]] = None) -> Dict:
    db = db or Database()
    exams = exams or list(REALEXAM_FILES.keys())
    results = {}
    for exam in exams:
        results[exam] = sync_realexam(exam, db=db)
    return {"synced": results}
