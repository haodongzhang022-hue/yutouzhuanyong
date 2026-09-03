"""数据库模块测试"""
import os
import sys
import tempfile

# 保证能找到 src 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import Database


def make_db():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, 'test_physics.db')
    return Database(db_path), db_path


def test_db_init():
    db, path = make_db()
    assert os.path.exists(path), "数据库文件应被创建"


def test_save_and_get_question():
    db, _ = make_db()
    q = {
        "exam_type": "ap_physics_1",
        "question_type": "multiple_choice",
        "source": "测试源",
        "external_id": "test-001",
        "topic": "kinematics",
        "difficulty": "easy",
        "question_text": "测试题目？",
        "options": ["A", "B", "C", "D"],
        "correct_answer": "A",
        "explanation": "解析内容"
    }
    ok = db.save_question(q)
    assert ok, "题目应保存成功"

    # 获取
    questions = db.get_questions(exam_type="ap_physics_1")
    assert len(questions) == 1
    assert questions[0]['question_text'] == "测试题目？"
    assert questions[0]['options'] == ["A", "B", "C", "D"]


def test_save_duplicate():
    db, _ = make_db()
    q = {
        "exam_type": "ap_physics_1",
        "external_id": "dup-001",
        "question_text": "重复题目",
        "correct_answer": "A",
    }
    assert db.save_question(q)
    assert not db.save_question(q), "重复题不应再次保存"
    assert db.count_questions("ap_physics_1") == 1


def test_get_daily_questions():
    db, _ = make_db()
    # 保存多题
    for i in range(8):
        db.save_question({
            "exam_type": "physics_bowl_d1",
            "external_id": f"q{i}",
            "question_text": f"物理碗题目{i}",
            "correct_answer": "A",
        })
    questions = db.get_daily_questions("physics_bowl_d1", count=5)
    assert len(questions) == 5, "每日应返回指定数量题目"


def test_stats():
    db, _ = make_db()
    for i in range(3):
        db.save_question({
            "exam_type": "ap_physics_1",
            "external_id": f"a{i}",
            "question_text": f"AP题目{i}",
            "correct_answer": "B",
        })
    for i in range(2):
        db.save_question({
            "exam_type": "physics_bowl_d1",
            "external_id": f"b{i}",
            "question_text": f"碗题目{i}",
            "correct_answer": "C",
        })
    stats = db.get_stats()
    assert stats['ap_physics_1'] == 3
    assert stats['physics_bowl_d1'] == 2
    assert stats['total'] == 5
