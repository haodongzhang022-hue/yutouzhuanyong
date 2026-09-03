"""真题/练习 · 三种可下载产物（题目only / 答案only / 题目+答案）。

复用 paper_builder 的题源加载与规范化（练习+真题合并、按知识点归组），
为每个知识点落 3 个可单独下载/转 PDF 的 Markdown 产物：

  {exam}_KP{nn}_题目卷.md      → 只下载题目（隐藏答案）
  {exam}_KP{nn}_答案卡.md      → 只下载答案（含解析、不带题干）
  {exam}_KP{nn}_含答案.md      → 题目+答案 全卷下载

产物落在 data/download/{exam}/，并写 DOWNLOAD.md 目录入口。
"""
from __future__ import annotations
import os
from typing import Dict, List, Optional

from src.paths import DATA_DIR, PROJECT_ROOT
from src.models.database import Database
from src.organization.kp_catalog import KnowledgePointCatalog
from src.organization.topic_index import TopicIndex
from src.services.paper_builder import _load_bank
from src.organization.paper_renderer import (
    render_paper, render_answer_sheet, paper_filename,
)

DEFAULT_DL_DIR = os.path.join(DATA_DIR, "download")


def _dl_filename(exam: str, kp_en: str, kp_code: str, kind: str) -> str:
    ascii_part = kp_en.replace(" ", "_") if kp_en else kp_code
    ascii_part = "".join(c for c in ascii_part if c.isalnum() or c in "_-")
    num = kp_code[2:] if kp_code.startswith("KP") else kp_code
    return f"{exam}_KP{num}_{ascii_part}_{kind}.md"


def export_exam(exam: str, catalog: KnowledgePointCatalog,
                outdir: str = DEFAULT_DL_DIR,
                db: Optional[Database] = None) -> Dict:
    """导出某考试全部知识点的三份可下载产物。"""
    raw = _load_bank(exam)
    kp_of, kp_name_of = {}, {}
    for q in raw:
        topic = q.get("topic", "")
        kp = catalog.resolve(topic)
        kp_of[topic] = kp
        kp_name_of[kp] = catalog.kp_name(kp)
    norm = normalize_for_export(raw, exam, kp_of, kp_name_of)
    index = TopicIndex(norm)
    grouped = index.group_by_kp()

    exam_dir = os.path.join(outdir, exam)
    os.makedirs(exam_dir, exist_ok=True)
    files: List[str] = []
    for kp_code in sorted(grouped, key=lambda c: int(c[2:])):
        qs = grouped[kp_code]
        kp_name = catalog.kp_name(kp_code)
        kp_en = catalog.kp_name_en(kp_code)
        module = catalog.module(kp_code)
        # 题目卷（隐藏答案）
        qf = os.path.join(exam_dir, _dl_filename(exam, kp_en, kp_code, "题目卷"))
        with open(qf, "w", encoding="utf-8") as fp:
            fp.write(render_paper(kp_code, kp_name, kp_en, module, exam, qs,
                                  with_answer=False))
        # 答案卡（只答案/解析）
        af = os.path.join(exam_dir, _dl_filename(exam, kp_en, kp_code, "答案卡"))
        with open(af, "w", encoding="utf-8") as fp:
            fp.write(render_answer_sheet(qs))
        # 含答案全卷
        fa = os.path.join(exam_dir, _dl_filename(exam, kp_en, kp_code, "含答案"))
        with open(fa, "w", encoding="utf-8") as fp:
            fp.write(render_paper(kp_code, kp_name, kp_en, module, exam, qs,
                                  with_answer=True))
        files.append(paper_filename(exam, kp_en, kp_code, with_answer=False))

    _write_download_index(exam_dir, exam, grouped, catalog)
    if db is not None:
        db.log_paper_run(exam, trigger="export", total_papers=len(files),
                         status="success", message="三种下载产物导出",
                         version="dl-3mode")
    return {"exam": exam, "kp_groups": len(grouped), "questions": len(norm)}


def _write_download_index(exam_dir, exam, grouped, catalog):
    lines = [f"# {exam} · 下载区", "",
             "> 每知识点含 3 种可下载文件：**题目卷**（隐藏答案）／"
             "**答案卡**（只含答案解析）／**含答案**（题目+答案全卷）。", ""]
    for kp_code in sorted(grouped, key=lambda c: int(c[2:])):
        kp_name = catalog.kp_name(kp_code)
        kp_en = catalog.kp_name_en(kp_code)
        lines += [f"## {kp_name} `{kp_code}`（{len(grouped[kp_code])}题）",
                  f"- 📄 只下载题：`{_dl_filename(exam,kp_en,kp_code,'题目卷')}`",
                  f"- 🔑 只下载答案：`{_dl_filename(exam,kp_en,kp_code,'答案卡')}`",
                  f"- 📦 题+答案：`{_dl_filename(exam,kp_en,kp_code,'含答案')}`", ""]
    with open(os.path.join(exam_dir, "DOWNLOAD.md"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


# 局部 import 避免循环依赖：在函数内复用 paper_builder 的归一化
def normalize_for_export(raw, exam, kp_of, kp_name_of):
    from src.organization.question_normalizer import normalize_batch
    return normalize_batch(raw, exam, kp_of, kp_name_of)


def export_all(exams: Optional[List[str]] = None,
               db: Optional[Database] = None) -> Dict:
    catalog = KnowledgePointCatalog()
    from src.services.paper_builder import EXAM_FILES
    exams = exams or list(EXAM_FILES.keys())
    results = {}
    for exam in exams:
        results[exam] = export_exam(exam, catalog, db=db)
    return {"exported": results}
