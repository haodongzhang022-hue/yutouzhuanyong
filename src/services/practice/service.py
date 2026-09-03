"""M4 · 练习领域服务（作答闭环）。

职责：
- 开会话：按 exam / kp_code / 题型 / 难度 选出指定数量题目（隐藏答案下发）。
- 提交判分：逐题比对正确答案，记录 practice_attempts，自动收录错题。
- 错题本 / 复习掌握 / 进度统计 / 学习计划。
只依赖 Database；API 层负责 HTTP 出入。
"""
from __future__ import annotations

import uuid
import logging
import random
from datetime import date
from typing import Dict, List, Optional

from src.models.database import Database

logger = logging.getLogger(__name__)


class PracticeService:
    def __init__(self, db: Database = None):
        self.db = db or Database()

    # ------------------------------------------------------------------
    # 会话
    # ------------------------------------------------------------------
    def open_session(self, user_key: str, exam_type: str = None,
                     kp_code: str = None, qtype: str = None,
                     difficulty: str = None, count: int = 5,
                     exclude_ids: list = None) -> Dict:
        """开一个作答会话，返回题干（隐藏答案）。"""
        count = min(max(int(count or 5), 1), 30)
        questions = self.db.get_questions(
            exam_type=exam_type, limit=count, offset=0,
            topic=None, difficulty=difficulty,
            kp_code=kp_code, qtype=qtype)
        # 过滤已做（可选手动排除）
        if exclude_ids:
            exset = set(exclude_ids)
            questions = [q for q in questions if q["id"] not in exset]
        # 随机取 count 道
        random.shuffle(questions)
        questions = questions[:count]

        sid = f"prac_{user_key}_{uuid.uuid4().hex[:8]}"
        payload = [{
            "question_id": q["id"],
            "exam_type": q["exam_type"],
            "question_type": q.get("question_type", "multiple_choice"),
            "topic": q.get("topic"),
            "kp_code": q.get("kp_code"),
            "difficulty": q.get("difficulty"),
            "question_text": q["question_text"],
            "options": q.get("options", []),
            # 隐藏答案与解析
        } for q in questions]
        return {
            "session_id": sid,
            "user_key": user_key,
            "count": len(payload),
            "questions": payload,
            "total_available": len(questions),
        }

    # ------------------------------------------------------------------
    # 判分
    # ------------------------------------------------------------------
    def submit(self, session_id: str, user_key: str,
               answers: List[Dict], response_ms: int = None) -> Dict:
        """提交整份答卷：逐题判分，记录 attempt，错题自动收录。"""
        results = []
        n_correct = 0
        mistakes = []
        for ans in answers:
            qid = ans.get("question_id")
            user_answer = ans.get("user_answer", "")
            q = self.db.get_question_by_id(qid)
            if not q:
                continue
            correct = self._is_correct(q, user_answer)
            if correct:
                n_correct += 1
            else:
                mistakes.append(qid)
                self.db.add_mistake(user_key, qid)
            self.db.save_attempt(session_id, user_key, qid,
                                 str(user_answer), correct,
                                 response_ms=response_ms)
            results.append({
                "question_id": qid,
                "user_answer": user_answer,
                "correct": correct,
                "correct_answer": q.get("correct_answer"),
                "explanation": q.get("explanation") if not correct else None,
            })
        total = len(results)
        return {
            "session_id": session_id,
            "total": total,
            "correct": n_correct,
            "score": round(n_correct / total, 4) if total else 0.0,
            "mistakes": mistakes,
            "results": results,
        }

    @staticmethod
    def _is_correct(q: Dict, user_answer) -> bool:
        expected = q.get("correct_answer")
        if expected is None:
            return False
        return str(expected).strip().lower() == str(user_answer or "").strip().lower()

    # ------------------------------------------------------------------
    # 错题本 / 复习
    # ------------------------------------------------------------------
    def list_mistakes(self, user_key: str, exam_type: str = None,
                      only_pending: bool = True) -> Dict:
        mastered = 0 if only_pending else None
        rows = self.db.list_mistakes(user_key, exam_type=exam_type,
                                     mastered=mastered)
        return {"user_key": user_key, "mistakes": rows,
                "total": len(rows)}

    def review_mistake(self, user_key: str, question_id: int,
                       mastered: bool = True) -> bool:
        """复习错题：默认标记掌握。"""
        self.db.update_mistake_review(user_key, question_id, mastered=mastered)
        return True

    def stats(self, user_key: str) -> Dict:
        s = self.db.stats_for_user(user_key)
        s["user_key"] = user_key
        return s

    # ------------------------------------------------------------------
    # 学习计划
    # ------------------------------------------------------------------
    def create_plan(self, user_key: str, exam_type: str, kp_code: str = None,
                    difficulty: str = None, daily_target: int = 5) -> Dict:
        pid = self.db.create_plan(user_key, exam_type, kp_code,
                                  difficulty, daily_target)
        return {"plan_id": pid, "user_key": user_key}

    def list_plans(self, user_key: str) -> Dict:
        return {"user_key": user_key, "plans": self.db.list_plans(user_key)}

    def toggle_plan(self, user_key: str, plan_id: int,
                    enabled: bool) -> Dict:
        ok = self.db.set_plan_enabled(user_key, plan_id, enabled)
        return {"ok": ok, "plan_id": plan_id, "enabled": enabled}
