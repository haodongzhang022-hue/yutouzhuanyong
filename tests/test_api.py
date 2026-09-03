"""API 接口测试（V2：改用 create_app 工厂注入，去模块级全局态依赖）"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import Database
from src.api.server import create_app


def setup_module():
    """测试前准备：用临时数据库 + 工厂注入构建隔离的 app。"""
    global test_db, app
    tmpdir = tempfile.mkdtemp()
    test_db = Database(os.path.join(tmpdir, 'api_test.db'))

    for i in range(5):
        test_db.save_question({
            "exam_type": "ap_physics_1",
            "external_id": f"api-q-{i}",
            "question_type": "multiple_choice",
            "source": "测试源",
            "topic": "kinematics",
            "difficulty": "easy",
            "question_text": f"AP物理1测试题{i}？",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "A",
            "explanation": f"这是题{i}的解析"
        })
    for i in range(3):
        test_db.save_question({
            "exam_type": "physics_bowl_d1",
            "external_id": f"api-pb-{i}",
            "question_type": "multiple_choice",
            "source": "测试源",
            "topic": "dynamics",
            "difficulty": "medium",
            "question_text": f"物理碗D1测试题{i}？",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "B",
            "explanation": f"这是题{i}的解析"
        })

    app = create_app(db=test_db)
    app.config['TESTING'] = True


def test_health():
    client = app.test_client()
    r = client.get('/api/health')
    assert r.status_code == 200
    assert r.json['status'] == 'ok'


def test_health_live():
    client = app.test_client()
    r = client.get('/api/health/live')
    assert r.status_code == 200
    assert r.json['status'] == 'up'


def test_health_ready():
    client = app.test_client()
    r = client.get('/api/health/ready')
    assert r.status_code in (200, 503)


def test_stats():
    client = app.test_client()
    r = client.get('/api/stats')
    assert r.status_code == 200
    assert r.json['code'] == 0
    assert r.json['data']['stats']['ap_physics_1'] == 5
    assert r.json['data']['stats']['physics_bowl_d1'] == 3
    assert r.json['data']['stats']['total'] == 8


def test_questions_list():
    client = app.test_client()
    r = client.get('/api/questions?exam_type=ap_physics_1&limit=3')
    assert r.status_code == 200
    assert len(r.json['data']['questions']) == 3
    assert r.json['data']['total'] == 5


def test_daily_practice_hides_answer():
    client = app.test_client()
    r = client.get('/api/daily/ap_physics_1?count=3&practice_mode=true')
    assert r.status_code == 200
    for q in r.json['data']['questions']:
        assert 'correct_answer' not in q
        assert 'explanation' not in q


def test_daily_practice_shows_answer():
    client = app.test_client()
    r = client.get('/api/daily/ap_physics_1?count=2&practice_mode=false')
    assert r.status_code == 200
    for q in r.json['data']['questions']:
        assert 'correct_answer' in q


def test_invalid_exam_type():
    client = app.test_client()
    r = client.get('/api/daily/unknown_type')
    assert r.status_code == 400
    assert r.json['code'] == 1


def test_get_single_question():
    client = app.test_client()
    r = client.get('/api/questions?exam_type=ap_physics_1&limit=1')
    qid = r.json['data']['questions'][0]['id']
    r2 = client.get(f'/api/questions/{qid}')
    assert r2.status_code == 200
    assert r2.json['code'] == 0


def test_papers_list():
    """专项卷目录接口可访问（返回结构正确即可）。"""
    client = app.test_client()
    r = client.get('/api/papers?exam_type=ap_physics_1')
    assert r.status_code == 200
    assert r.json['code'] == 0
    assert 'papers' in r.json['data']


def test_metrics():
    client = app.test_client()
    r = client.get('/api/metrics')
    assert r.status_code == 200
    assert 'api_requests_total' in r.get_data(as_text=True)
