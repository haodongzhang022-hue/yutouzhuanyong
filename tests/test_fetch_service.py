"""抓取服务测试"""
import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import Database
from src.services.fetch_service import FetchService

# 项目根目录
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _builtin_count(exam_type):
    """动态读取内置题库题目数量"""
    path_map = {
        'ap_physics_1': 'data/builtin/ap_physics_1.json',
        'physics_bowl_d1': 'data/builtin/physics_bowl_d1.json',
    }
    with open(os.path.join(ROOT, path_map[exam_type]), 'r', encoding='utf-8') as f:
        return len(json.load(f))


def test_builtin_fetch():
    """测试从内置题库抓取"""
    tmpdir = tempfile.mkdtemp()
    db = Database(os.path.join(tmpdir, 'test.db'))

    config = {
        'collectors': {
            'ap_physics_1': {
                'enabled': True,
                'per_source_limit': 5,
                'sources': [
                    {
                        'name': '内置题库',
                        'type': 'builtin',
                        'path': 'data/builtin/ap_physics_1.json',
                        'limit': 5
                    }
                ]
            },
            'physics_bowl_d1': {
                'enabled': True,
                'per_source_limit': 5,
                'sources': [
                    {
                        'name': '内置题库',
                        'type': 'builtin',
                        'path': 'data/builtin/physics_bowl_d1.json',
                        'limit': 5
                    }
                ]
            }
        }
    }

    service = FetchService(db=db, config=config)

    results = service.fetch_daily(exam_types=['ap_physics_1'], daily_count=5)
    assert results['ap_physics_1']['new'] > 0, "应能获取到题目"
    assert results['ap_physics_1']['total_fetched'] > 0
    assert db.count_questions('ap_physics_1') > 0

    results = service.fetch_daily(exam_types=['physics_bowl_d1'], daily_count=5)
    assert results['physics_bowl_d1']['new'] > 0
    assert db.count_questions('physics_bowl_d1') > 0


def test_save_duplicate_question():
    """同一道题不应重复保存（去重逻辑直接测试）"""
    tmpdir = tempfile.mkdtemp()
    db = Database(os.path.join(tmpdir, 'test.db'))
    q = {
        "exam_type": "ap_physics_1",
        "external_id": "same-q-001",
        "question_text": "同一道题",
        "correct_answer": "A",
    }
    assert db.save_question(q), "首次保存成功"
    assert not db.save_question(q), "重复题不应再次保存"
    assert db.count_questions('ap_physics_1') == 1


def test_force_fetch_all():
    """全量拉取应获取数据源所有题目"""
    tmpdir = tempfile.mkdtemp()
    db = Database(os.path.join(tmpdir, 'test.db'))
    config = {
        'collectors': {
            'ap_physics_1': {
                'enabled': True,
                'per_source_limit': 3,
                'sources': [
                    {'name': '内置题库', 'type': 'builtin',
                     'path': 'data/builtin/ap_physics_1.json', 'limit': 3}
                ]
            }
        }
    }
    service = FetchService(db=db, config=config)

    expected = _builtin_count('ap_physics_1')
    # 全量拉取应该拿到内置题库全部题目
    results = service.force_fetch_all()
    assert results['ap_physics_1']['total_fetched'] == expected, \
        f"全量拉取应获取全部内置题目，实际 {results['ap_physics_1']['total_fetched']}"
    assert db.count_questions('ap_physics_1') == expected
