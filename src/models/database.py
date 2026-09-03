"""数据库模型模块 - 使用 SQLite 存储题库数据"""
import os
import sqlite3
import json
import logging
from datetime import datetime, date
from typing import List, Dict, Optional

from src.paths import DEFAULT_DB_PATH

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
                        difficulty, question_text, options, correct_answer, explanation)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
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
                        question.get('explanation', '')
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
