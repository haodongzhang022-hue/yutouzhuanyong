"""V3 真题溯源 + 三种下载产物 测试。"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import Database
from src.organization.paper_renderer import (
    render_paper, render_answer_sheet, provenance_tag,
)


def _fresh_db():
    tmpdir = tempfile.mkdtemp()
    return Database(os.path.join(tmpdir, 're.db'))


def _real_q():
    return {
        "exam_type": "ap_physics_1", "question_type": "multiple_choice",
        "source": "真题源", "external_id": "real-ap1-2018-q1",
        "topic": "kinematics", "difficulty": "medium",
        "question_text": "真题题干", "options": ["A", "B", "C", "D"],
        "correct_answer": "A", "explanation": "真题解析",
        "is_real": 1, "exam_year": 2018, "paper": "卷B",
        "q_no": 1, "points": 6,
    }


def test_save_realexam_persists_provenance():
    db = _fresh_db()
    assert db.save_question(_real_q())
    row = db.get_question_by_id(1)
    assert row["is_real"] == 1
    assert row["exam_year"] == 2018
    assert row["paper"] == "卷B"
    assert row["q_no"] == 1
    assert row["points"] == 6


def test_realexam_stats_and_gaps():
    db = _fresh_db()
    q = _real_q()
    db.save_question(q)
    # 一道缺溯源（无题号/分值）来制造 gap
    bad = dict(q, external_id="real-bad", exam_year=None, q_no=None,
               points=None)
    db.save_question(bad)
    assert db.count_realexam() == 2
    assert db.count_realexam(exam_type="ap_physics_1",
                             year_from=2018, year_to=2018) == 1
    assert db.realexam_by_year() == {2018: 1}
    gaps = db.realexam_gaps(exam_type="ap_physics_1")
    assert len(gaps) == 1 and gaps[0]["external_id"] == "real-bad"


def test_realexam_import_log():
    db = _fresh_db()
    db.log_realexam_import("ap_physics_1", "ap1-2010-2024", 2010, 2024, 3)
    logs = db.latest_realexam_imports(exam_type="ap_physics_1")
    assert logs and logs[0]["batch"] == "ap1-2010-2024"
    assert logs[0]["count"] == 3


def _norm_q(extra=None):
    base = {
        "qid": "AP1-KP01-Q01", "exam": "ap_physics_1",
        "kp_code": "KP01", "kp_name": "运动学", "type": "mc",
        "difficulty": "medium", "stem": "题干", "options": ["A", "B", "C", "D"],
        "answer": "A", "explanation": "解析", "source_ref": "x",
        "is_real": 1, "exam_year": 2018, "paper": "卷B",
        "q_no": 3, "points": 6,
    }
    if extra:
        base.update(extra)
    return base


def test_provenance_tag():
    q = _norm_q()
    assert provenance_tag(q) == "【真题｜2018 · 卷B · 第3题 · 6分】"
    # 练习题无来源标注
    q2 = _norm_q({"is_real": 0})
    assert provenance_tag(q2) == ""


def test_answer_sheet_only_answers():
    q = _norm_q()
    sheet = render_answer_sheet([q])
    assert "题干" not in sheet, "答案卡不应含题干"
    assert "答案：`A`" in sheet
    assert "真题｜2018 · 卷B · 第3题 · 6分" in sheet


def test_render_paper_marks_real_source_and_omits_answer():
    q = _norm_q()
    paper = render_paper("KP01", "运动学", "Kinematics", "力学",
                         "ap_physics_1", [q], with_answer=False)
    assert "真题｜2018 · 卷B · 第3题 · 6分" in paper
    assert "答案：`A`" not in paper, "题目卷应隐藏答案"
    ans = render_paper("KP01", "运动学", "Kinematics", "力学",
                       "ap_physics_1", [q], with_answer=True)
    assert "答案：`A`" in ans
    assert "来源：【真题｜2018 · 卷B · 第3题 · 6分】" in ans
