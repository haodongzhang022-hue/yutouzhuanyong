"""
知识点 / 题型 / 难度 双向索引（让 AI 与系统能"按类型找题"）

输入规范化题目列表，构建三类索引：
  by_kp[qid], by_type[qid], by_difficulty[qid]
任意组合查询 = 取交集。
"""
from __future__ import annotations
from typing import Dict, List


class TopicIndex:
    def __init__(self, questions: List[Dict] = None):
        self.questions = questions or []
        self.by_kp: Dict[str, List[str]] = {}
        self.by_type: Dict[str, List[str]] = {}
        self.by_difficulty: Dict[str, List[str]] = {}
        self._build()

    def _build(self):
        for q in self.questions:
            qid_ = q["qid"]
            self.by_kp.setdefault(q["kp_code"], []).append(qid_)
            self.by_type.setdefault(q["type"], []).append(qid_)
            self.by_difficulty.setdefault(q["difficulty"], []).append(qid_)

    def query(self, kp_code: str = None, qtype: str = None,
              difficulty: str = None) -> List[str]:
        """任意维度过滤，返回匹配 qid 列表（取交集）。"""
        sets = []
        if kp_code:
            sets.append(set(self.by_kp.get(kp_code, [])))
        if qtype:
            sets.append(set(self.by_type.get(qtype, [])))
        if difficulty:
            sets.append(set(self.by_difficulty.get(difficulty, [])))
        if not sets:
            return [q["qid"] for q in self.questions]
        return sorted(set.intersection(*sets))

    def group_by_kp(self) -> Dict[str, List[Dict]]:
        """按知识点分组的题，供渲染一份份专项卷。"""
        grouped: Dict[str, List[Dict]] = {}
        for q in self.questions:
            grouped.setdefault(q["kp_code"], []).append(q)
        return grouped
