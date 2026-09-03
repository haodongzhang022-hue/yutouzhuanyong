"""
专项练习卷渲染器（像学生试卷那样）

把一个知识点下的全部题，排成一份人类可读的 Markdown 试卷。
题目卷不含答案（with_answer=False），解析卷含答案（with_answer=True）。

版式：卷头 / 题型小节 / 逐题 / (可选)答案与解析。
"""
from __future__ import annotations
from typing import Dict, List

_EXAM_TITLE = {
    "ap_physics_1": "AP Physics 1",
    "physics_bowl_d1": "Physics Bowl D1",
}
_TYPE_TITLE = {"mc": "单选题", "fr": "解答题"}
_CN_NUM = ["一", "二", "三", "四", "五"]


def provenance_tag(q: Dict) -> str:
    """生成真题来源标注：如『真题｜2018 · 卷B · 第3题 · 6分』。
    仅当该题标记为真题且带年份时输出，练习题为空字符串。"""
    if not (q.get("is_real") and q.get("exam_year")):
        return ""
    parts = [f"{q['exam_year']}"]
    if q.get("paper"):
        parts.append(q["paper"])
    if q.get("q_no") is not None:
        parts.append(f"第{q['q_no']}题")
    if q.get("points") is not None:
        pt = q["points"]
        parts.append(f"{pt:g}分" if isinstance(pt, float) else f"{pt}分")
    return f"【真题｜{' · '.join(parts)}】"


def render_paper(
    kp_code: str,
    kp_name: str,
    kp_name_en: str,
    module: str,
    exam: str,
    questions: List[Dict],
    with_answer: bool = False,
) -> str:
    """渲染一份专项练习卷，返回 Markdown 全文。"""
    exam_title = _EXAM_TITLE.get(exam, exam)
    mc = [q for q in questions if q["type"] == "mc"]
    fr = [q for q in questions if q["type"] == "fr"]

    # 卷头
    n_mc, n_fr = len(mc), len(fr)
    diff: Dict[str, int] = {}
    for q in questions:
        diff[q["difficulty"]] = diff.get(q["difficulty"], 0) + 1
    diff_str = "/".join(f"{d}:{c}" for d, c in sorted(diff.items()))
    type_desc = "、".join(t for t, c in [("单选", n_mc), ("解答", n_fr)] if c)
    title = f"{exam_title} · 专项练习 · {kp_name} {kp_name_en}"

    lines: List[str] = [
        f"# {title}",
        "",
        f"> **模块**：{module}｜**知识点**：`{kp_code}`｜**题量**：{len(questions)}",
        f"> **题型**：{type_desc}｜**难度分布**：{diff_str}",
        f"> **建议用时**：约 {max(10, len(questions) * 4)} 分钟",
        "",
        "---",
        "",
    ]

    # 卷内题号连续
    seg = 1
    section = 0
    # ---- 单选题 ----
    if mc:
        section += 1
        lines += [f"## {_CN_NUM[section - 1]}、{_TYPE_TITLE['mc']}（共 {n_mc} 题）", "",
                  "> 从 A/B/C/D 中选择唯一正确答案。", ""]
        for q in mc:
            tag = provenance_tag(q)
            head = f"**{seg}. {q['stem']}**"
            if tag:
                head = f"**{seg}.** {tag} {q['stem']}"
            lines.append(head)
            lines.append("")
            for li, opt in enumerate(q["options"]):
                letter = chr(ord("A") + li)
                lines.append(f"- {letter}. {opt}")
            lines += ["", "---", ""]
            seg += 1

    # ---- 解答题 ----
    if fr:
        section += 1
        lines += [f"## {_CN_NUM[section - 1]}、{_TYPE_TITLE['fr']}（共 {n_fr} 题）", ""]
        for q in fr:
            tag = provenance_tag(q)
            head = f"**{seg}. {q['stem']}**"
            if tag:
                head = f"**{seg}.** {tag} {q['stem']}"
            lines.append(head)
            lines.append("")
            lines.append("请写出完整解题过程：")
            lines += ["", "> 作答区：", "", "---", ""]
            seg += 1

    # 解析卷：追加参考答案与解析
    if with_answer:
        lines += ["", "## 📖 参考答案与解析", ""]
        for i, q in enumerate(questions, start=1):
            ans = q.get("answer", "")
            expl = q.get("explanation", "")
            src_lines = []
            tag = provenance_tag(q)
            if tag:
                src_lines.append(f"- 来源：{tag}")
            # 仅真题显示来源；练习题答案卷不附加来源，保持整洁
            lines += [f"**{i}. {q['stem']}**", "",
                      f"- 答案：`{ans}`"] + src_lines
            if q.get("key_points"):
                lines.append(f"- 知识点要点：{q['key_points']}")
            lines += [f"- 解析：{expl}", ""]
    return "\n".join(lines).rstrip() + "\n"


def _num(kp_code: str) -> str:
    return kp_code[2:] if kp_code.startswith("KP") else kp_code


def paper_filename(exam: str, kp_name_en: str, kp_code: str,
                   with_answer: bool = False) -> str:
    """专项卷文件名：{exam}_KP{序号}_{English}.md / .answer.md"""
    ascii_part = kp_name_en.replace(" ", "_") if kp_name_en else kp_code
    ascii_part = "".join(c for c in ascii_part if c.isalnum() or c in "_-")
    base = f"{exam}_KP{_num(kp_code)}_{ascii_part}"
    return f"{base}.answer.md" if with_answer else f"{base}.md"


def render_answer_sheet(questions: List[Dict]) -> str:
    """只下载"答案"用的独立答案卡：不含题干，按卷内题号 + 真题来源对齐。"""
    lines: List[str] = ["# 参考答案卡", "",
                        "> 仅含答案与解析，便于对照；题号与该知识点题目卷一致。", ""]
    for i, q in enumerate(questions, start=1):
        tag = provenance_tag(q)
        src = f"｜{tag}" if tag else ""
        src_ref = q.get("source_ref")
        src2 = f"（{src_ref}）" if src_ref and not tag else ""
        lines += [f"### {i}. 题号 {i}{src}{src2}",
                  f"- 答案：`{q.get('answer','')}`"]
        if q.get("key_points"):
            lines.append(f"- 知识点要点：{q['key_points']}")
        lines += [f"- 解析：{q.get('explanation','')}", ""]
    return "\n".join(lines).rstrip() + "\n"
