"""Schema v2：题库组织索引列 + 专项卷/练习相关表。

升级内容：
1. questions 表新增派生列：kp_code / kp_name / norm_type / norm_qid（M2 回填，只读派生）。
2. 新增 paper_runs 表（M3 卷构建登记，寻址/版本）。
3. 新增 practice_attempts / mistakes / study_plans 表（M4 练习闭环）。
"""
from __future__ import annotations

import logging

from src.models.migrations import migration

logger = logging.getLogger(__name__)


def _has_column(conn, table: str, column: str) -> bool:
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


@migration(2)
def upgrade(conn):
    # ---- questions 派生列（M2）----
    conn.execute("BEGIN")
    for col, ddl in (("kp_code", "TEXT"), ("kp_name", "TEXT"),
                     ("norm_type", "TEXT"), ("norm_qid", "TEXT")):
        if not _has_column(conn, "questions", col):
            conn.execute(f"ALTER TABLE questions ADD COLUMN {col} {ddl}")
    for idx, col in (("idx_questions_kp", "kp_code"),
                     ("idx_questions_norm_type", "norm_type")):
        conn.execute(f"CREATE INDEX IF NOT EXISTS {idx} ON questions({col})")
    conn.execute("COMMIT")

    # ---- 专项卷构建登记（M3）----
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS paper_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_type TEXT NOT NULL,
        trigger TEXT DEFAULT 'manual',
        built_at TEXT DEFAULT (datetime('now','localtime')),
        total_papers INTEGER DEFAULT 0,
        status TEXT DEFAULT 'success',
        message TEXT,
        version TEXT
    );
    """)

    # ---- 练习闭环表（M4）----
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS practice_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        user_key TEXT NOT NULL,
        question_id INTEGER NOT NULL,
        submitted_at TEXT DEFAULT (datetime('now','localtime')),
        user_answer TEXT,
        is_correct INTEGER DEFAULT 0,
        response_ms INTEGER
    );
    CREATE INDEX IF NOT EXISTS idx_attempts_session ON practice_attempts(session_id);
    CREATE INDEX IF NOT EXISTS idx_attempts_user ON practice_attempts(user_key);

    CREATE TABLE IF NOT EXISTS mistakes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_key TEXT NOT NULL,
        question_id INTEGER NOT NULL,
        added_at TEXT DEFAULT (datetime('now','localtime')),
        review_count INTEGER DEFAULT 0,
        mastered INTEGER DEFAULT 0,
        UNIQUE(user_key, question_id)
    );
    CREATE INDEX IF NOT EXISTS idx_mistakes_user ON mistakes(user_key);

    CREATE TABLE IF NOT EXISTS study_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_key TEXT NOT NULL,
        exam_type TEXT,
        kp_code TEXT,
        difficulty TEXT,
        daily_target INTEGER DEFAULT 5,
        enabled INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    """)
    logger.info("Schema v2 迁移完成")
