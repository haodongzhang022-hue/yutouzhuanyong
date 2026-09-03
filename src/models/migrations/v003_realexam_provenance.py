"""Schema v3：真题(real-exam) 溯源列 + 真题录入登记表。

升级内容：
1. questions 表新增真题溯源列（只读派生/录入时写入）：
   is_real  / exam_year / paper(卷/套) / q_no(卷内题号) / points(分值)。
2. 新增 realexam_imports 表：登记每次"真题批量导入"（溯源缺口审计 / 全量不漏校验）。
"""
from __future__ import annotations

import logging

from src.models.migrations import migration

logger = logging.getLogger(__name__)


def _has_column(conn, table: str, column: str) -> bool:
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


@migration(3)
def upgrade(conn):
    conn.execute("BEGIN")
    for col, ddl in (("is_real", "INTEGER DEFAULT 0"),
                     ("exam_year", "INTEGER"),
                     ("paper", "TEXT"),
                     ("q_no", "INTEGER"),
                     ("points", "REAL")):
        if not _has_column(conn, "questions", col):
            conn.execute(f"ALTER TABLE questions ADD COLUMN {col} {ddl}")
    for idx, col in (("idx_questions_real", "is_real"),
                     ("idx_questions_year", "exam_year")):
        conn.execute(f"CREATE INDEX IF NOT EXISTS {idx} ON questions({col})")
    conn.execute("COMMIT")

    conn.executescript("""
    CREATE TABLE IF NOT EXISTS realexam_imports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_type TEXT NOT NULL,
        batch TEXT NOT NULL,          -- 批次标识，如 'ap_physics_1-2010-2024'
        year_from INTEGER,
        year_to INTEGER,
        count INTEGER DEFAULT 0,      -- 本批导入新增真题数
        status TEXT DEFAULT 'success',
        message TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    """)
    logger.info("Schema v3 迁移完成（真题溯源列 + 导入登记）")
