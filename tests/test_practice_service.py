"""M4 练习领域服务测试：会话/判分/错题/统计/计划。"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import Database
from src.services.practice.service import PracticeService


def _setup(n=10):
    tmpdir = tempfile.mkdtemp()
    db = Database(os.path.join(tmpdir, 'prac.db'))
    for i in range(n):
        db.save_question({
            "exam_type": "ap_physics_1",
            "external_id": f"p-{i}",
            "question_text": f"AP题{i}？",
            "correct_answer": "A",
            "options": ["A", "B", "C", "D"],
            "topic": "kinematics",
            "difficulty": "easy",
            "explanation": "解析",
            "question_type": "multiple_choice",
        })
    return db, PracticeService(db)


def test_open_session_hides_answer():
    db, svc = _setup()
    sess = svc.open_session("u1", "ap_physics_1", count=5)
    assert sess['count'] == 5
    assert sess['session_id'].startswith('prac_u1_')
    for q in sess['questions']:
        assert 'correct_answer' not in q, "开会话不应泄露答案"
        assert 'explanation' not in q


def test_submit_scores_and_records():
    db, svc = _setup()
    sess = svc.open_session("u1", "ap_physics_1", count=5)
    # 全对（答案都是 A/B，取 options 第一个 'A'）
    answers = [{"question_id": q['question_id'], "user_answer": "A"}
               for q in sess['questions']]
    res = svc.submit(sess['session_id'], "u1", answers)
    assert res['total'] == 5
    assert res['correct'] == res['total']
    assert res['score'] == 1.0
    assert len(res['mistakes']) == 0
    assert db.count_questions('ap_physics_1') == 10
    assert len(db.get_attempts_by_session(sess['session_id'])) == 5


def test_wrong_answer_creates_mistake():
    db, svc = _setup()
    sess = svc.open_session("u1", "ap_physics_1", count=5)
    # 全答错：用一个肯定不对的答案 'Z'
    answers = [{"question_id": q['question_id'], "user_answer": "Z"}
               for q in sess['questions']]
    res = svc.submit(sess['session_id'], "u1", answers)
    assert res['correct'] == 0
    assert len(res['mistakes']) == 5
    mist = svc.list_mistakes("u1")
    assert mist['total'] == 5


def test_review_mistake_marks_mastered():
    db, svc = _setup()
    sess = svc.open_session("u1", "ap_physics_1", count=3)
    answers = [{"question_id": q['question_id'], "user_answer": "Z"}
               for q in sess['questions']]
    svc.submit(sess['session_id'], "u1", answers)
    qid = sess['questions'][0]['question_id']
    svc.review_mistake("u1", qid, mastered=True)
    # pending (mastered=0) 只剩 2 条
    pending = svc.list_mistakes("u1", only_pending=True)
    assert pending['total'] == 2


def test_stats_accuracy():
    db, svc = _setup(4)
    sess = svc.open_session("u1", "ap_physics_1", count=4)
    # 前两个对，后两个错
    answers = []
    for i, q in enumerate(sess['questions']):
        answers.append({"question_id": q['question_id'],
                        "user_answer": "A" if i < 2 else "Z"})
    svc.submit(sess['session_id'], "u1", answers)
    st = svc.stats("u1")
    assert st['total_attempts'] == 4
    assert st['correct_attempts'] == 2
    assert st['accuracy'] == 0.5


def test_create_and_list_plans():
    db, svc = _setup()
    p = svc.create_plan("u1", "ap_physics_1", kp_code="KP01",
                        daily_target=3)
    assert p['plan_id'] > 0
    plans = svc.list_plans("u1")['plans']
    assert len(plans) == 1
    assert plans[0]['daily_target'] == 3
    # 停用后不再列出
    svc.toggle_plan("u1", p['plan_id'], enabled=False)
    assert svc.list_plans("u1")['plans'] == []
