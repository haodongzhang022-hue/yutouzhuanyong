"""M3 · 专项卷生产服务（组织层流水线 + 卷登记）。

把 `scripts/organize_bank.py` 的核心逻辑抽成可被 API / 调度器调用的服务：
- 读取 data/builtin（或 DB questions）→ 规范化 → 归组 → 渲染题目卷+解析卷
- 产出 data/papers/{exam}/ 并写 INDEX / ai_index
- 把每次构建登记到 paper_runs 表（版本寻址）
"""
from __future__ import annotations

import json
import os
from collections import OrderedDict
from typing import Dict, List, Optional

from src.paths import DATA_DIR, PROJECT_ROOT
from src.models.database import Database
from src.organization.kp_catalog import KnowledgePointCatalog
from src.organization.question_normalizer import normalize_batch
from src.organization.topic_index import TopicIndex
from src.organization.paper_renderer import render_paper, paper_filename

BUILTIN_DIR = os.path.join(PROJECT_ROOT, "data", "builtin")
EXAM_FILES = {
    "ap_physics_1": os.path.join(BUILTIN_DIR, "ap_physics_1.json"),
    "physics_bowl_d1": os.path.join(BUILTIN_DIR, "physics_bowl_d1.json"),
}
DEFAULT_OUTDIR = os.path.join(DATA_DIR, "papers")


def _module_rows(grouped, catalog, exam):
    rows_by_module: Dict[str, list] = OrderedDict()
    for kp_code in sorted(grouped, key=lambda c: int(c[2:])):
        qs = grouped[kp_code]
        kp_name = catalog.kp_name(kp_code)
        kp_en = catalog.kp_name_en(kp_code)
        module = catalog.module(kp_code)
        f_q = paper_filename(exam, kp_en, kp_code, with_answer=False)
        f_a = paper_filename(exam, kp_en, kp_code, with_answer=True)
        n_mc = sum(1 for q in qs if q["type"] == "mc")
        n_fr = len(qs) - n_mc
        row = (f"- **{kp_name}** (`{kp_code}`)｜{module}｜{len(qs)}题"
               f"（单选{n_mc}/解答{n_fr}）｜📄 `{f_q}`｜📖 `{f_a}`")
        rows_by_module.setdefault(module, []).append(row)
    return rows_by_module


def _write_index(exam_dir, exam, rows_by_module):
    lines = [f"# {exam} · 专项练习目录", "",
             "> 按知识点组织：每个知识点 = 一份专项练习卷。"
             "题目卷用于作答，解析卷用于复盘。", ""]
    for module, rows in rows_by_module.items():
        lines += [f"## {module}", ""] + rows + [""]
    os.makedirs(exam_dir, exist_ok=True)
    with open(os.path.join(exam_dir, "INDEX.md"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def _write_ai_index(exam_dir, exam, grouped, catalog):
    payload = {"exam": exam, "by_knowledge_point": []}
    for kp_code in sorted(grouped, key=lambda c: int(c[2:])):
        payload["by_knowledge_point"].append({
            "kp_code": kp_code,
            "kp_name": catalog.kp_name(kp_code),
            "kp_name_en": catalog.kp_name_en(kp_code),
            "module": catalog.module(kp_code),
            "count": len(grouped[kp_code]),
            "questions": grouped[kp_code],
        })
    with open(os.path.join(exam_dir, "ai_index.json"), "w",
              encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def organize_exam(exam: str, catalog: KnowledgePointCatalog,
                  outdir: str = DEFAULT_OUTDIR,
                  db: Optional[Database] = None,
                  trigger: str = "manual", version: str = "v2.0") -> Dict:
    """组织单个考试，产出专项卷并（可选）登记 paper_run。"""
    raw_qs = json.load(open(EXAM_FILES[exam], encoding="utf-8"))
    kp_of, kp_name_of = {}, {}
    for q in raw_qs:
        topic = q.get("topic", "")
        kp = catalog.resolve(topic)
        kp_of[topic] = kp
        kp_name_of[kp] = catalog.kp_name(kp)
    norm = normalize_batch(raw_qs, exam, kp_of, kp_name_of)
    index = TopicIndex(norm)
    grouped = index.group_by_kp()

    exam_dir = os.path.join(outdir, exam)
    os.makedirs(exam_dir, exist_ok=True)
    n_papers = 0
    for kp_code in sorted(grouped, key=lambda c: int(c[2:])):
        qs = grouped[kp_code]
        kp_name = catalog.kp_name(kp_code)
        kp_en = catalog.kp_name_en(kp_code)
        module = catalog.module(kp_code)
        with open(os.path.join(exam_dir,
                               paper_filename(exam, kp_en, kp_code,
                                              with_answer=False)),
                  "w", encoding="utf-8") as fp:
            fp.write(render_paper(kp_code, kp_name, kp_en, module,
                                  exam, qs, with_answer=False))
        with open(os.path.join(exam_dir,
                               paper_filename(exam, kp_en, kp_code,
                                              with_answer=True)),
                  "w", encoding="utf-8") as fp:
            fp.write(render_paper(kp_code, kp_name, kp_en, module,
                                  exam, qs, with_answer=True))
        n_papers += 1

    rows_by_module = _module_rows(grouped, catalog, exam)
    _write_index(exam_dir, exam, rows_by_module)
    _write_ai_index(exam_dir, exam, grouped, catalog)

    if db is not None:
        db.log_paper_run(exam, trigger=trigger, total_papers=n_papers,
                         status="success", version=version)
    return {"exam": exam, "papers": n_papers, "questions": len(norm)}


def rebuild_papers(exams: Optional[List[str]] = None, db: Optional[Database] = None,
                   kp_code: Optional[str] = None) -> Dict:
    """重建全部/指定考试专项卷；kp_code 目前整考试重建（产出已含各卷）。"""
    catalog = KnowledgePointCatalog()
    exams = exams or list(EXAM_FILES.keys())
    results = {}
    for exam in exams:
        if exam not in EXAM_FILES:
            results[exam] = {"error": f"未知考试 {exam}"}
            continue
        results[exam] = organize_exam(exam, catalog,
                                      db=db, trigger="manual",
                                      version=f"v2-{exam}")
    return {"rebuilt": results}
