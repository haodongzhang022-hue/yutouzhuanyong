#!/usr/bin/env python3
"""
一键组织题库：平铺 JSON -> 知识点专项练习卷（人可读试卷）+ 结构化 AI 索引 + 试卷目录

用法：
    python scripts/organize_bank.py                        # 组织 data/builtin 全部题库
    python scripts/organize_bank.py --exam ap_physics_1    # 只处理指定考试
    python scripts/organize_bank.py --outdir data/papers   # 指定试卷输出目录
"""
from __future__ import annotations
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.organization.kp_catalog import KnowledgePointCatalog          # noqa: E402
from src.organization.question_normalizer import normalize_batch        # noqa: E402
from src.organization.topic_index import TopicIndex                     # noqa: E402
from src.organization.paper_renderer import render_paper, paper_filename  # noqa: E402

BUILTIN = os.path.join(ROOT, "data", "builtin")
EXAM_FILES = {
    "ap_physics_1": os.path.join(BUILTIN, "ap_physics_1.json"),
    "physics_bowl_d1": os.path.join(BUILTIN, "physics_bowl_d1.json"),
}


def _load_builtin(exam: str):
    with open(EXAM_FILES[exam], "r", encoding="utf-8") as f:
        return json.load(f)


def _module_rows(grouped, catalog, exam):
    """按模块排序返回每知识点一行目录文本。"""
    from collections import OrderedDict
    rows_by_module = OrderedDict()
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
             f"> 按知识点组织：每个知识点 = 一份专项练习卷。题目卷用于作答，解析卷用于复盘。", ""]
    for module, rows in rows_by_module.items():
        lines += [f"## {module}", ""] + rows + [""]
    with open(os.path.join(exam_dir, "INDEX.md"), "w", encoding="utf-8") as f:
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
    with open(os.path.join(exam_dir, "ai_index.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def organize_exam(exam: str, catalog: KnowledgePointCatalog, outdir: str):
    raw_qs = _load_builtin(exam)

    # 原始 topic -> kp_code / kp_code -> 中文名 映射
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

    for kp_code in sorted(grouped, key=lambda c: int(c[2:])):
        qs = grouped[kp_code]
        kp_name = catalog.kp_name(kp_code)
        kp_en = catalog.kp_name_en(kp_code)
        module = catalog.module(kp_code)
        # 题目卷（隐藏答案）
        f_q = paper_filename(exam, kp_en, kp_code, with_answer=False)
        with open(os.path.join(exam_dir, f_q), "w", encoding="utf-8") as fp:
            fp.write(render_paper(kp_code, kp_name, kp_en, module,
                                  exam, qs, with_answer=False))
        # 解析卷（含答案）
        f_a = paper_filename(exam, kp_en, kp_code, with_answer=True)
        with open(os.path.join(exam_dir, f_a), "w", encoding="utf-8") as fp:
            fp.write(render_paper(kp_code, kp_name, kp_en, module,
                                  exam, qs, with_answer=True))
        print(f"  ✔ {kp_code} {kp_name}（{kp_en}）: {len(qs)} 题")

    rows_by_module = _module_rows(grouped, catalog, exam)
    _write_index(exam_dir, exam, rows_by_module)
    _write_ai_index(exam_dir, exam, grouped, catalog)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exam", default=None,
                    help="exam: ap_physics_1 / physics_bowl_d1（默认全部）")
    ap.add_argument("--outdir", default=os.path.join(ROOT, "data", "papers"))
    args = ap.parse_args()
    catalog = KnowledgePointCatalog()
    exams = [args.exam] if args.exam else list(EXAM_FILES.keys())
    for exam in exams:
        print(f"[organize] {exam}")
        organize_exam(exam, catalog, args.outdir)
    print("完成。专项卷已输出到:", os.path.abspath(args.outdir))


if __name__ == "__main__":
    main()
