"""M4/M5 练习闭环 API 测试：会话/提交/错题/统计/计划/重建。"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import Database
from src.api.server import create_app
from src.services.fetch_service import FetchService
from src.services.practice.service import PracticeService


def setup_module():
    global app, db
    tmpdir = tempfile.mkdtemp()
    db = Database(os.path.join(tmpdir, 'papi.db'))
    for i in range(8):
        db.save_question({
            "exam_type": "ap_physics_1",
            "external_id": f"pa-{i}",
            "question_type": "multiple_choice",
            "source": "测试源",
            "topic": "kinematics",
            "difficulty": "easy",
            "question_text": f"API题{i}？",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "A",
            "explanation": f"解析{i}",
        })
    fs = FetchService(db=db, rebuild=False)
    ps = PracticeService(db=db)
    app = create_app(db=db, fetch_service=fs, practice_service=ps)
    app.config['TESTING'] = True


def test_open_session_api():
    c = app.test_client()
    r = c.post('/api/practice/session',
               json={"user_key": "u", "exam_type": "ap_physics_1",
                     "count": 5})
    assert r.status_code == 200
    assert r.json['code'] == 0
    assert r.json['data']['count'] == 5
    for q in r.json['data']['questions']:
        assert 'correct_answer' not in q


def test_submit_full_flow():
    c = app.test_client()
    r = c.post('/api/practice/session',
               json={"user_key": "u2", "exam_type": "ap_physics_1",
                     "count": 4})
    sid = r.json['data']['session_id']
    qs = r.json['data']['questions']
    answers = [{"question_id": q['question_id'], "user_answer": "A"}
               for q in qs]
    r = c.post(f'/api/practice/session/{sid}/submit',
               json={"user_key": "u2", "answers": answers})
    assert r.json['data']['score'] == 1.0
    assert r.json['data']['correct'] == 4
    # 错题本应为空
    r = c.get('/api/practice/mistakes?user_key=u2')
    assert r.json['data']['total'] == 0


def test_mistake_flow_api():
    c = app.test_client()
    r = c.post('/api/practice/session',
               json={"user_key": "u3", "exam_type": "ap_physics_1",
                     "count": 3})
    sid = r.json['data']['session_id']
    qs = r.json['data']['questions']
    answers = [{"question_id": q['question_id'], "user_answer": "Z"}
               for q in qs]
    c.post(f'/api/practice/session/{sid}/submit',
           json={"user_key": "u3", "answers": answers})
    r = c.get('/api/practice/mistakes?user_key=u3')
    assert r.json['data']['total'] == 3
    # 复习一条
    qid = r.json['data']['mistakes'][0]['question_id']
    r2 = c.post(f'/api/practice/mistakes/{qid}/review',
                json={"user_key": "u3", "mastered": True})
    assert r2.json['code'] == 0
    r3 = c.get('/api/practice/mistakes?user_key=u3')
    assert r3.json['data']['total'] == 2


def test_stats_and_plans_api():
    c = app.test_client()
    r = c.get('/api/practice/stats?user_key=u2')
    assert r.json['data']['total_attempts'] == 4
    assert r.json['data']['accuracy'] == 1.0
    r = c.post('/api/study/plans',
               json={"user_key": "u2", "exam_type": "ap_physics_1",
                     "kp_code": "KP01", "daily_target": 3})
    plan_id = r.json['data']['plan_id']
    assert r.json['code'] == 0
    r = c.get('/api/study/plans?user_key=u2')
    assert len(r.json['data']['plans']) == 1
    r = c.delete(f'/api/study/plans/{plan_id}?user_key=u2')
    assert r.json['code'] == 0
    r = c.get('/api/study/plans?user_key=u2')
    assert r.json['data']['plans'] == []


def test_submit_missing_answers_400():
    c = app.test_client()
    r = c.post('/api/practice/session/whatever/submit',
               json={"user_key": "u", "answers": []})
    assert r.status_code == 400


def test_rebuild_papers_api():
    c = app.test_client()
    r = c.post('/api/rebuild/papers', json={"exam_type": "ap_physics_1"})
    assert r.status_code == 200
    assert r.json['data']['ap_physics_1']['papers'] > 0


def test_paper_runs_endpoint():
    c = app.test_client()
    r = c.get('/api/papers/runs')
    assert r.status_code == 200
    assert 'data' in r.json
