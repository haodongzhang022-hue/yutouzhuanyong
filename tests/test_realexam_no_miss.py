"""V3.1 真题 no-miss 对账（全量不漏）测试。"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import Database
from src.services import realexam_manifest as rm
from src.services.realexam_sync import sync_realexam, load_realexam_json


def _fresh_db():
    tmpdir = tempfile.mkdtemp()
    return Database(os.path.join(tmpdir, 're.db'))


def _real_q(year=2015, paper="FR", qno=1, pid=1, external=None):
    return {
        "exam_type": "ap_physics_1", "question_type": "multiple_choice",
        "source": "真题源",
        "external_id": external or f"real-ap1-{year}-{pid}",
        "topic": "kinematics", "difficulty": "medium",
        "question_text": f"真题题干 {year}-{pid}",
        "options": ["A", "B", "C", "D"],
        "correct_answer": "A", "explanation": "解析",
        "is_real": 1, "exam_year": year, "paper": paper,
        "q_no": qno, "points": 6,
    }


def test_audit_reports_missing_papers():
    db = _fresh_db()
    # 只入 2015·FR，其余(2016..今年)应判缺
    db.save_question(_real_q(2015, "FR", 1, 1))
    coverage = db.realexam_paper_coverage("ap_physics_1")
    cur = 2024
    a = rm.audit_realexam("ap_physics_1", coverage, current_year=cur)
    assert a["audited"] is True
    assert a["complete"] is False
    assert a["present_total"] == 1
    # 应缺 2016..2024 各一年·FR
    missing_years = sorted(y for (y, p) in a["missing"])
    assert missing_years == list(range(2016, cur + 1))
    assert (2015, "FR") in a["present"]


def test_audit_complete_when_all_papers_present():
    db = _fresh_db()
    cur = 2020
    for y in range(2015, cur + 1):
        db.save_question(_real_q(y, "FR", 1, y))
    coverage = db.realexam_paper_coverage("ap_physics_1")
    a = rm.audit_realexam("ap_physics_1", coverage, current_year=cur)
    assert a["complete"] is True
    assert a["missing"] == []
    assert a["expected_total"] == a["present_total"] == (cur - 2015 + 1)


def test_sync_realexam_idempotent_and_dedup():
    # 用临时文件替换 realexam json 路径做注入测试
    import json as _json
    tmp = tempfile.mkdtemp()
    exam_file = os.path.join(tmp, "ap_physics_1.json")
    with open(exam_file, "w", encoding="utf-8") as f:
        _json.dump([_real_q(2015, "FR", 1, 1, external="real-x1"),
                    _real_q(2015, "FR", 2, 2, external="real-x2")], f)

    # 临时覆写 REALEXAM_FILES 指向测试文件
    import src.services.realexam_sync as mod
    from src.services.paper_builder import REALEXAM_FILES
    original = REALEXAM_FILES["ap_physics_1"]
    REALEXAM_FILES["ap_physics_1"] = exam_file
    db = _fresh_db()
    try:
        r1 = sync_realexam("ap_physics_1", db=db, rebuild=False)
        assert r1["new"] == 2
        # 再次同步应为幂等，不重复入库
        r2 = sync_realexam("ap_physics_1", db=db, rebuild=False)
        assert r2["new"] == 0
        assert db.count_realexam(exam_type="ap_physics_1") == 2
    finally:
        REALEXAM_FILES["ap_physics_1"] = original


def test_load_realexam_json_sets_defaults():
    records = load_realexam_json("ap_physics_1")
    assert isinstance(records, list)
    for r in records:
        assert r.get("is_real") == 1
        assert r.get("exam_type") == "ap_physics_1"
