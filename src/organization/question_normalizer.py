"""
单题规范化器（Question Normalizer）

把采集源里的"平铺原始题"规范成统一的 qid / type / kp_code，
供知识点索引与专项练习卷渲染使用。不回写原始采集数据。
"""
from __future__ import annotations
from typing import Dict, List

# 考试体系 -> qid 前缀
_EXAM_PREFIX = {
    "ap_physics_1": "AP1",
    "physics_bowl_d1": "PB",
}

# 原始 question_type 长名 -> 短编码
_TYPE_MAP = {
    "multiple_choice": "mc",
    "free_response": "fr",
}


def norm_type(raw: str) -> str:
    """multiple_choice/free_response -> mc/fr；未知回退 mc"""
    return _TYPE_MAP.get((raw or "").strip(), "mc")


def qid(exam: str, kp_code: str, seq: int) -> str:
    """生成规范题号 EXAM-kp_code-Q<seq>"""
    prefix = _EXAM_PREFIX.get(exam, exam.upper())
    return f"{prefix}-{kp_code}-Q{seq:02d}"


def normalize_question(
    raw: Dict,
    exam: str,
    kp_code: str,
    seq: int,
    kp_name: str = "",
) -> Dict:
    """把一条原始采集题规范化为统一结构"""
    options = raw.get("options") or []
    return {
        "qid": qid(exam, kp_code, seq),
        "exam": exam,
        "kp_code": kp_code,
        "kp_name": kp_name or raw.get("topic", ""),
        "type": norm_type(raw.get("question_type", "")),
        "difficulty": (raw.get("difficulty") or "medium"),
        "stem": raw.get("question_text", ""),
        "options": list(options),
        "answer": raw.get("correct_answer", ""),
        "explanation": raw.get("explanation", ""),
        "source_ref": raw.get("external_id", ""),
        # ---- V3 真题溯源：哪些数据可有则透传（练习题为空，真题必填）----
        "is_real": 1 if raw.get("is_real") else 0,
        "exam_year": raw.get("exam_year"),
        "paper": raw.get("paper", ""),
        "q_no": raw.get("q_no"),
        "points": raw.get("points"),
    }


def normalize_batch(raw_questions: List[Dict], exam: str,
                    kp_of: Dict[str, str],
                    kp_name_of: Dict[str, str]) -> List[Dict]:
    """
    批量规范化：kp_of 把原始 topic -> kp_code，
    kp_name_of 把 kp_code -> 中文名。
    同知识点内按出现顺序编 Q 序号。
    """
    out: List[Dict] = []
    counter: Dict[str, int] = {}
    for raw in raw_questions:
        topic = raw.get("topic", "")
        kp = kp_of.get(topic, topic)  # 归并，未匹配则沿用原文
        counter[kp] = counter.get(kp, 0) + 1
        kp_name = kp_name_of.get(kp, topic)
        out.append(normalize_question(raw, exam, kp, counter[kp], kp_name))
    return out
