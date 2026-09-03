"""V2 Schema 迁移测试：v0/v1 -> v2 幂等，kp/norm 派生列 + 练习/卷表。"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import Database
from src.models.migrations import run_migrations


def _fresh_db():
    tmpdir = tempfile.mkdtemp()
    return Database(os.path.join(tmpdir, 'mig.db'))


def test_schema_v2_columns_present():
    db = _fresh_db()
    conn = db._get_conn()
    cols = {r['name'] for r in conn.execute(
        "PRAGMA table_info(questions)").fetchall()}
    for col in ("kp_code", "kp_name", "norm_type", "norm_qid"):
        assert col in cols, f"缺派生列 {col}"


def test_practice_tables_created():
    db = _fresh_db()
    conn = db._get_conn()
    tabs = {r['name'] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    for t in ("practice_attempts", "mistakes", "study_plans", "paper_runs"):
        assert t in tabs, f"缺表 {t}"


def test_user_version_is_latest():
    # v003 将 schema 推进到 3（真题溯源列 + 导入登记表）
    from src.models.migrations import SCHEMA_VERSION
    db = _fresh_db()
    assert db._get_conn().execute(
        "PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 3


def test_schema_v3_realexam_columns_present():
    db = _fresh_db()
    conn = db._get_conn()
    cols = {r['name'] for r in conn.execute(
        "PRAGMA table_info(questions)").fetchall()}
    for col in ("is_real", "exam_year", "paper", "q_no", "points"):
        assert col in cols, f"缺真题溯源列 {col}"
    tabs = {r['name'] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "realexam_imports" in tabs, "缺真题导入登记表"


def test_migration_idempotent():
    db = _fresh_db()
    # 再次运行不应报错 / 不应重复建列
    run_migrations(db._get_conn())
    conn = db._get_conn()
    n = len([r for r in conn.execute(
        "PRAGMA table_info(questions)").fetchall()
        if r['name'] == 'kp_code'])
    assert n == 1, "kp_code 不应被重复添加"


def test_mistake_unique_constraint():
    db = _fresh_db()
    db.save_question({"exam_type": "ap_physics_1", "external_id": "m1",
                      "question_text": "q?", "correct_answer": "A"})
    qid = db.get_questions(exam_type="ap_physics_1")[0]['id']
    db.add_mistake("u", qid)
    db.add_mistake("u", qid)
    assert db.count_mistakes("u") == 1, "错题重复收录应去重"
