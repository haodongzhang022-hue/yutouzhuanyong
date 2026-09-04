"""数据库模型模块 - 使用 SQLite 存储题库数据"""
import os
import sqlite3
import json
import logging
from datetime import datetime, date
from typing import List, Dict, Optional

from src.paths import DEFAULT_DB_PATH
from src.models import migrations as _migrations

logger = logging.getLogger(__name__)


class Database:
    """SQLite 数据库封装，负责题目数据的持久化存储"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = DEFAULT_DB_PATH
        self.db_path = os.path.abspath(db_path)
        # 确保目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        """初始化数据库表结构"""
        with self._get_conn() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_type TEXT NOT NULL,          -- 'ap_physics_1' 或 'physics_bowl_d1'
                question_type TEXT NOT NULL,      -- 'multiple_choice' / 'free_response'
                source TEXT,                      -- 题目来源
                external_id TEXT,                 -- 外部题目 ID
                topic TEXT,                       -- 主题/知识点
                difficulty TEXT DEFAULT 'medium', -- 难度: easy/medium/hard
                question_text TEXT NOT NULL,      -- 题目内容
                options TEXT,                     -- 选择题选项 JSON
                correct_answer TEXT NOT NULL,     -- 正确答案
                explanation TEXT,                 -- 解析
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                UNIQUE(exam_type, external_id, question_text)
            );

            CREATE TABLE IF NOT EXISTS fetch_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_type TEXT NOT NULL,
                source_name TEXT,
                fetched_date TEXT NOT NULL,
                fetched_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'success',    -- success / partial / failed
                message TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            """)
        # V2：schema 迁移到最新版本（v0/v1 -> v2，加 kp/norm 派生列与练习表）
        _migrations.run_migrations(self._get_conn())
        logger.info("数据库初始化完成: %s", self.db_path)

    # ---------- 题目操作 ----------

    def save_question(self, question: Dict) -> bool:
        """保存单道题目，已存在则跳过"""
        try:
            with self._get_conn() as conn:
                # 先查重
                cur = conn.execute(
                    "SELECT id FROM questions WHERE exam_type=? AND external_id=?",
                    (question.get('exam_type', ''),
                     question.get('external_id', ''))
                )
                if cur.fetchone():
                    return False
                conn.execute(
                    """INSERT INTO questions
                       (exam_type, question_type, source, external_id, topic,
                        difficulty, question_text, options, correct_answer,
                        explanation, is_real, exam_year, paper, q_no, points)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        question.get('exam_type', ''),
                        question.get('question_type', 'multiple_choice'),
                        question.get('source', ''),
                        question.get('external_id', ''),
                        question.get('topic', ''),
                        question.get('difficulty', 'medium'),
                        question.get('question_text', ''),
                        json.dumps(question.get('options', []), ensure_ascii=False),
                        question.get('correct_answer', ''),
                        question.get('explanation', ''),
                        1 if question.get('is_real') else 0,
                        question.get('exam_year'),
                        question.get('paper', ''),
                        question.get('q_no'),
                        question.get('points')
                    )
                )
                return True
        except Exception as e:
            logger.error("保存题目失败: %s", e)
            return False

    def save_questions(self, questions: List[Dict]) -> int:
        """批量保存题目，返回新增数量"""
        count = 0
        for q in questions:
            if self.save_question(q):
                count += 1
        return count

    def get_questions(self, exam_type: str = None, limit: int = 10,
                      offset: int = 0, topic: str = None,
                      difficulty: str = None,
                      kp_code: str = None, qtype: str = None) -> List[Dict]:
        """查询题目列表。

        V2：支持按 kp_code / 题型短码(qtype) 筛选；当 questions 表存在
        对应列时才应用筛选，保证兼容 v1 schema（见 src/core/migrations 计划）。
        """
        sql = "SELECT * FROM questions WHERE 1=1"
        params = []
        if exam_type:
            sql += " AND exam_type=?"
            params.append(exam_type)
        if topic:
            sql += " AND topic=?"
            params.append(topic)
        if difficulty:
            sql += " AND difficulty=?"
            params.append(difficulty)
        cols = self._table_columns("questions")
        if kp_code and "kp_code" in cols:
            sql += " AND kp_code=?"
            params.append(kp_code)
        if qtype and "norm_type" in cols:
            sql += " AND norm_type=?"
            params.append(qtype)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if item.get('options'):
                try:
                    item['options'] = json.loads(item['options'])
                except (json.JSONDecodeError, TypeError):
                    item['options'] = []
            result.append(item)
        return result

    def get_question_by_id(self, question_id: int) -> Optional[Dict]:
        """按 ID 获取单题"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM questions WHERE id=?", (question_id,)
            ).fetchone()
        if not row:
            return None
        item = dict(row)
        if item.get('options'):
            try:
                item['options'] = json.loads(item['options'])
            except (json.JSONDecodeError, TypeError):
                item['options'] = []
        return item

    def get_daily_questions(self, exam_type: str, count: int = 5,
                            exclude_ids: list = None) -> List[Dict]:
        """获取今日练习题目（可排除已做过题目）"""
        sql = "SELECT * FROM questions WHERE exam_type=?"
        params = [exam_type]
        if exclude_ids:
            placeholders = ','.join('?' * len(exclude_ids))
            sql += f" AND id NOT IN ({placeholders})"
            params.extend(exclude_ids)
        sql += " ORDER BY RANDOM() LIMIT ?"
        params.append(count)

        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if item.get('options'):
                try:
                    item['options'] = json.loads(item['options'])
                except (json.JSONDecodeError, TypeError):
                    item['options'] = []
            result.append(item)
        return result

    def count_questions(self, exam_type: str = None) -> int:
        """统计题目数量"""
        sql = "SELECT COUNT(*) as cnt FROM questions"
        params = []
        if exam_type:
            sql += " WHERE exam_type=?"
            params.append(exam_type)
        with self._get_conn() as conn:
            row = conn.execute(sql, params).fetchone()
        return row['cnt'] if row else 0

    def get_stats(self) -> Dict:
        """获取统计信息"""
        stats = {'ap_physics_1': 0, 'physics_bowl_d1': 0, 'total': 0}
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT exam_type, COUNT(*) as cnt FROM questions GROUP BY exam_type"
            ).fetchall()
        total = 0
        for row in rows:
            exam = row['exam_type']
            cnt = row['cnt']
            total += cnt
            if exam in stats:
                stats[exam] = cnt
        stats['total'] = total
        return stats

    # ---------- 抓取日志 ----------

    def log_fetch(self, exam_type: str, source_name: str, fetched_date: str,
                  fetched_count: int, status: str = 'success',
                  message: str = '') -> None:
        """记录一次抓取日志"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO fetch_logs
                       (exam_type, source_name, fetched_date, fetched_count, status, message)
                       VALUES (?,?,?,?,?,?)""",
                    (exam_type, source_name, fetched_date, fetched_count, status, message)
                )
        except Exception as e:
            logger.error("记录抓取日志失败: %s", e)

    def get_fetch_logs(self, limit: int = 20) -> List[Dict]:
        """获取最近抓取日志"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM fetch_logs ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    # ---------- V2：组织索引列支持（kp_code / type）----------
    def _table_columns(self, table: str = "questions") -> set:
        """返回表的现有列名集合（用于兼容 v1/v2 schema 差异）。"""
        with self._get_conn() as conn:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {r["name"] for r in rows}

    # =====================================================================
    # V2：M4 练习闭环 数据访问（practice_attempts / mistakes / study_plans）
    # =====================================================================

    # ---------- 作答会话与判分 ----------
    def save_attempt(self, session_id: str, user_key: str, question_id: int,
                     user_answer: str, is_correct: bool,
                     response_ms: int = None) -> int:
        """记录一次作答，返回 attempt id。"""
        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO practice_attempts
                   (session_id, user_key, question_id, user_answer,
                    is_correct, response_ms)
                   VALUES (?,?,?,?,?,?)""",
                (session_id, user_key, question_id, user_answer,
                 1 if is_correct else 0, response_ms))
            return cur.lastrowid

    def get_attempts_by_session(self, session_id: str) -> List[Dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM practice_attempts WHERE session_id=? ORDER BY id",
                (session_id,)).fetchall()
        return [dict(r) for r in rows]

    # ---------- 错题本 ----------
    def add_mistake(self, user_key: str, question_id: int) -> bool:
        """收录错题（存在则跳过）。返回是否新增。"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO mistakes(user_key, question_id)"
                    " VALUES (?,?)", (user_key, question_id))
                return conn.total_changes > 0
        except Exception as e:  # noqa: BLE001
            logger.error("收录错题失败: %s", e)
            return False

    def list_mistakes(self, user_key: str, exam_type: str = None,
                      mastered: int = None) -> List[Dict]:
        """错题本（join questions 取题详情）。"""
        sql = ("SELECT m.*, q.exam_type, q.question_text, q.options, "
               "q.correct_answer, q.explanation, q.kp_code, q.difficulty "
               "FROM mistakes m JOIN questions q ON q.id=m.question_id "
               "WHERE m.user_key=?")
        params = [user_key]
        if exam_type:
            sql += " AND q.exam_type=?"
            params.append(exam_type)
        if mastered is not None:
            sql += " AND m.mastered=?"
            params.append(mastered)
        sql += " ORDER BY m.added_at DESC"
        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d['options'] = json.loads(d['options']) if d.get('options') else []
            except (json.JSONDecodeError, TypeError):
                d['options'] = []
            out.append(d)
        return out

    def update_mistake_review(self, user_key: str, question_id: int,
                              mastered: bool = None,
                              review_inc: bool = True) -> None:
        with self._get_conn() as conn:
            if mastered is not None:
                conn.execute(
                    "UPDATE mistakes SET mastered=?, review_count=review_count+1 "
                    "WHERE user_key=? AND question_id=?",
                    (1 if mastered else 0, user_key, question_id))
            elif review_inc:
                conn.execute(
                    "UPDATE mistakes SET review_count=review_count+1 "
                    "WHERE user_key=? AND question_id=?",
                    (user_key, question_id))

    def count_mistakes(self, user_key: str, mastered: int = None) -> int:
        sql = "SELECT COUNT(*) c FROM mistakes WHERE user_key=?"
        params = [user_key]
        if mastered is not None:
            sql += " AND mastered=?"
            params.append(mastered)
        with self._get_conn() as conn:
            return conn.execute(sql, params).fetchone()["c"]

    # ---------- 进度统计 ----------
    def stats_for_user(self, user_key: str) -> Dict:
        """用户作答统计：正确率 / 每题 / 错题数 / 最近连续打卡。"""
        with self._get_conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) c FROM practice_attempts WHERE user_key=?",
                (user_key,)).fetchone()["c"]
            correct = conn.execute(
                "SELECT COUNT(*) c FROM practice_attempts "
                "WHERE user_key=? AND is_correct=1", (user_key,)).fetchone()["c"]
            # 按 exam 分布
            by_exam_rows = conn.execute(
                "SELECT q.exam_type e, COUNT(*) c FROM practice_attempts a "
                "JOIN questions q ON q.id=a.question_id WHERE a.user_key=? "
                "GROUP BY q.exam_type", (user_key,)).fetchall()
            # 覆盖知识点数（答过题的知识点）
            kp_rows = conn.execute(
                "SELECT DISTINCT q.kp_code FROM practice_attempts a "
                "JOIN questions q ON q.id=a.question_id "
                "WHERE a.user_key=? AND q.kp_code IS NOT NULL",
                (user_key,)).fetchall()
        by_exam = {r["e"]: r["c"] for r in by_exam_rows}
        mistakes_total = self.count_mistakes(user_key)
        return {
            "total_attempts": total,
            "correct_attempts": correct,
            "accuracy": round(correct / total, 4) if total else 0.0,
            "by_exam": by_exam,
            "mistakes_pending": self.count_mistakes(user_key, mastered=0),
            "mistakes_total": mistakes_total,
            "kp_covered": [r["kp_code"] for r in kp_rows],
        }

    # ---------- 学习计划 ----------
    def create_plan(self, user_key: str, exam_type: str, kp_code: str = None,
                    difficulty: str = None, daily_target: int = 5) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO study_plans
                   (user_key, exam_type, kp_code, difficulty, daily_target)
                   VALUES (?,?,?,?,?)""",
                (user_key, exam_type, kp_code, difficulty, daily_target))
            return cur.lastrowid

    def list_plans(self, user_key: str) -> List[Dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM study_plans WHERE user_key=? "
                "AND enabled=1 ORDER BY created_at DESC", (user_key,)).fetchall()
        return [dict(r) for r in rows]

    def set_plan_enabled(self, user_key: str, plan_id: int, enabled: bool) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE study_plans SET enabled=? WHERE id=? AND user_key=?",
                (1 if enabled else 0, plan_id, user_key))
            return cur.rowcount > 0

    # ---------- M3：专项卷构建登记（paper_runs） ----------
    def log_paper_run(self, exam_type: str, trigger: str = "manual",
                      total_papers: int = 0, status: str = "success",
                      message: str = "", version: str = None) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO paper_runs
                   (exam_type, trigger, total_papers, status, message, version)
                   VALUES (?,?,?,?,?,?)""",
                (exam_type, trigger, total_papers, status, message, version))
            return cur.lastrowid

    def latest_paper_runs(self, exam_type: str = None, limit: int = 10) -> List[Dict]:
        sql = "SELECT * FROM paper_runs"
        params = []
        if exam_type:
            sql += " WHERE exam_type=?"
            params.append(exam_type)
        sql += " ORDER BY built_at DESC LIMIT ?"
        params.append(limit)
        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # =====================================================================
    # V3：真题(real-exam) 溯源 辅助访问
    # =====================================================================

    # ---------- 真题导入登记（realexam_imports） ----------
    def log_realexam_import(self, exam_type: str, batch: str,
                            year_from: int = None, year_to: int = None,
                            count: int = 0, status: str = "success",
                            message: str = "") -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO realexam_imports
                   (exam_type, batch, year_from, year_to, count, status, message)
                   VALUES (?,?,?,?,?,?,?)""",
                (exam_type, batch, year_from, year_to, count, status, message))
            return cur.lastrowid

    def latest_realexam_imports(self, exam_type: str = None,
                                limit: int = 10) -> List[Dict]:
        sql = "SELECT * FROM realexam_imports"
        params = []
        if exam_type:
            sql += " WHERE exam_type=?"
            params.append(exam_type)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # ---------- 真题统计 / 溯源缺口审计 ----------
    def count_realexam(self, exam_type: str = None,
                       year_from: int = None, year_to: int = None) -> int:
        """真题数量（可按年份区间过滤），用于"全量不漏"对账。"""
        sql = ("SELECT COUNT(*) c FROM questions "
               "WHERE is_real=1")
        params = []
        if exam_type:
            sql += " AND exam_type=?"
            params.append(exam_type)
        if year_from is not None:
            sql += " AND exam_year>=?"
            params.append(year_from)
        if year_to is not None:
            sql += " AND exam_year<=?"
            params.append(year_to)
        with self._get_conn() as conn:
            return conn.execute(sql, params).fetchone()["c"]

    def realexam_gaps(self, exam_type: str = None) -> List[Dict]:
        """溯源缺口审计：找出缺年份/卷内题号/分值的真题，避免漏标。"""
        sql = ("SELECT id, exam_type, external_id, exam_year, paper, "
               "q_no, points, kp_code FROM questions "
               "WHERE is_real=1 AND (exam_year IS NULL OR q_no IS NULL "
               "OR points IS NULL)")
        params = []
        if exam_type:
            sql += " AND exam_type=?"
            params.append(exam_type)
        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def realexam_by_year(self, exam_type: str = None) -> Dict[str, int]:
        """真题按年份分布，快速对账各年是否都已入库。"""
        sql = ("SELECT exam_year y, COUNT(*) c FROM questions "
               "WHERE is_real=1 AND exam_year IS NOT NULL")
        params = []
        if exam_type:
            sql += " AND exam_type=?"
            params.append(exam_type)
        sql += " GROUP BY exam_year ORDER BY y"
        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return {r["y"]: r["c"] for r in rows}

    def realexam_paper_coverage(self, exam_type: str = None
                                ) -> Dict[tuple, Dict]:
        """真题按 (年份, 卷/套) 覆盖情况，供 no-miss 对账引擎使用。

        返回 {(exam_year, paper): {"count": n, "papers_ok": bool, ...}}，
        paper 为空串的记录归到 paper=''（用于套卷标识未填写时的提示）。
        """
        sql = ("SELECT exam_year y, paper p, COUNT(*) c "
               "FROM questions WHERE is_real=1 AND exam_year IS NOT NULL")
        params = []
        if exam_type:
            sql += " AND exam_type=?"
            params.append(exam_type)
        sql += " GROUP BY exam_year, paper ORDER BY y"
        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        out: Dict[tuple, Dict] = {}
        for r in rows:
            p = r["p"] or ""
            out[(r["y"], p)] = {"count": r["c"], "year": r["y"], "paper": p}
        return out
