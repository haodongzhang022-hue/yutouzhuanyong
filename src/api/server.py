"""在线 API 服务 —— 提供题库查询、专项卷读取、练习与采集接口。

V2 改进：
- create_app(deps) 工厂注入，去除"硬编码全局 db/fetch_service"的耦合（D2）。
- 统一错误处理与响应体 {code,data|message}。
- 健康分级 live/ready + 指标端点。
- questions 支持 kp_code / type 结构化筛选（走索引列）。
- 专项卷读取端点 /api/papers。
仍保留模块级默认 app/db 供既有测试与简单启动兼容。
"""
import os
import logging
from flask import Flask, jsonify, request

from src.models.database import Database
from src.services.fetch_service import FetchService
from src.services.practice.service import PracticeService
from src.services.paper_builder import rebuild_papers as _rb
from src.core.metrics import metrics
from src.core.log import get_logger, new_request_id, set_request_id

logger = get_logger(__name__)

# 支持考试类型映射
EXAM_TYPE_ALIASES = {
    'ap_physics_1': 'ap_physics_1',
    'app1': 'ap_physics_1',
    'ap物理1': 'ap_physics_1',
    'physics_bowl_d1': 'physics_bowl_d1',
    'physical_bowl_d1': 'physics_bowl_d1',
    'pbd1': 'physics_bowl_d1',
    '物理碗d1': 'physics_bowl_d1',
    '物理碗D1': 'physics_bowl_d1',
}


def _normalize_exam_type(value: str) -> str:
    """标准化考试类型"""
    if not value:
        return None
    key = value.strip().lower()
    return EXAM_TYPE_ALIASES.get(key, key)


def _db_healthy(db) -> bool:
    try:
        db.count_questions()
        return True
    except Exception:  # noqa: BLE001
        return False


def create_app(db: Database = None, fetch_service: FetchService = None,
               practice_service: PracticeService = None) -> Flask:
    """工厂：注入依赖，构造独立 Flask 应用。"""
    db = db or Database()
    fetch_service = fetch_service or FetchService(db=db)
    practice_service = practice_service or PracticeService(db=db)
    app = Flask(__name__)

    # ---- 统一错误处理 ----
    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"code": 4041, "message": "资源不存在"}), 404

    @app.errorhandler(400)
    def bad_request(e):
        detail = getattr(e, "description", "参数错误")
        return jsonify({"code": 4001, "message": "参数错误",
                        "detail": str(detail)}), 400

    @app.errorhandler(500)
    def internal_error(e):
        logger.error("内部错误: %s", e)
        return jsonify({"code": 5001,
                        "message": "内部错误，请稍后重试"}), 500

    @app.before_request
    def _set_rid():
        set_request_id(new_request_id())


    @app.after_request
    def _metric(resp):
        metrics.inc("api_requests_total",
                    route=str(request.path), status=str(resp.status_code))
        return resp

    # ================= 健康与运维 =================
    @app.route('/api/health', methods=['GET'])
    def health():
        """兼容旧：总体健康。"""
        return jsonify({"status": "ok", "service": "AP Physics 专项练习系统",
                        "time": _now_str()})

    @app.route('/api/health/live', methods=['GET'])
    def health_live():
        return jsonify({"status": "up"})

    @app.route('/api/health/ready', methods=['GET'])
    def health_ready():
        checks = {"db": _db_healthy(db)}
        ready = all(checks.values())
        return jsonify({"status": "ready" if ready else "not_ready",
                        "checks": checks}), (200 if ready else 503)

    @app.route('/api/metrics', methods=['GET'])
    def metrics_endpoint():
        return metrics.render(), 200, {'Content-Type': 'text/plain'}

    # ================= 题库统计与查询 =================
    @app.route('/api/stats', methods=['GET'])
    def stats():
        data = db.get_stats()
        logs = db.get_fetch_logs(limit=5)
        return jsonify({"code": 0,
                        "data": {"stats": data, "recent_logs": logs}})

    @app.route('/api/questions', methods=['GET'])
    def get_questions():
        exam_type = _normalize_exam_type(request.args.get('exam_type', ''))
        limit = min(int(request.args.get('limit', 10)), 100)
        offset = int(request.args.get('offset', 0))
        topic = request.args.get('topic')
        difficulty = request.args.get('difficulty')
        kp_code = request.args.get('kp_code') or None
        qtype = request.args.get('type') or None

        questions = db.get_questions(
            exam_type=exam_type, limit=limit, offset=offset,
            topic=topic, difficulty=difficulty,
            kp_code=kp_code, qtype=qtype)
        total = db.count_questions(exam_type)
        metrics.set_gauge("questions_total", total,
                          exam=str(exam_type or "all"))
        return jsonify({"code": 0,
                        "data": {"total": total, "questions": questions}})

    @app.route('/api/questions/<int:qid>', methods=['GET'])
    def get_question(qid):
        question = db.get_question_by_id(qid)
        if not question:
            return jsonify({"code": 1, "message": "题目不存在"}), 404
        return jsonify({"code": 0, "data": question})

    # ================= 专项卷读取（V2） =================
    @app.route('/api/papers', methods=['GET'])
    def list_papers():
        """按考试（可选知识点）列出专项卷目录。"""
        exam = _normalize_exam_type(request.args.get('exam_type', ''))
        kp = request.args.get('kp_code')
        papers = fetch_service.list_papers(exam=exam, kp_code=kp)
        return jsonify({"code": 0, "data": {"papers": papers}})

    # ================= 每日练习 =================
    @app.route('/api/daily/<exam_type>', methods=['GET'])
    def get_daily(exam_type):
        exam = _normalize_exam_type(exam_type)
        if exam not in ('ap_physics_1', 'physics_bowl_d1'):
            return jsonify({"code": 1,
                            "message": "不支持的考试类型"}), 400
        count = min(int(request.args.get('count', 5)), 20)
        practice_mode = request.args.get('practice_mode',
                                         'true').lower() == 'true'
        questions = db.get_daily_questions(exam, count=count)
        if not questions:
            return jsonify({"code": 1, "message": "题库暂无可用题目，"
                            "请先执行采集任务",
                            "hint": "POST /api/fetch 触发一次采集"}), 404
        if practice_mode:
            for q in questions:
                q.pop('correct_answer', None)
                q.pop('explanation', None)
        return jsonify({"code": 0,
                        "data": {"exam_type": exam,
                                 "count": len(questions),
                                 "questions": questions}})

    # ================= 采集 =================
    @app.route('/api/fetch', methods=['POST'])
    def trigger_fetch():
        body = request.get_json(silent=True) or {}
        try:
            results = fetch_service.fetch_daily(
                exam_types=body.get('exam_types'),
                daily_count=body.get('count'))
            return jsonify({"code": 0, "message": "采集完成",
                            "data": results})
        except Exception as e:  # noqa: BLE001
            logger.error("手动触发采集失败: %s", e)
            return jsonify({"code": 1,
                            "message": f"采集失败: {e}"}), 500

    @app.route('/api/fetch/all', methods=['POST'])
    def trigger_fetch_all():
        try:
            results = fetch_service.force_fetch_all()
            return jsonify({"code": 0, "message": "全量采集完成",
                            "data": results})
        except Exception as e:  # noqa: BLE001
            logger.error("全量采集失败: %s", e)
            return jsonify({"code": 1,
                            "message": f"采集失败: {e}"}), 500

    # ================= 日志 =================
    @app.route('/api/logs', methods=['GET'])
    def get_logs():
        limit = min(int(request.args.get('limit', 20)), 100)
        logs = db.get_fetch_logs(limit=limit)
        return jsonify({"code": 0, "data": logs})


    # ================= V2 M4：练习闭环 =================
    @app.route('/api/practice/session', methods=['POST'])
    def open_practice():
        body = request.get_json(silent=True) or {}
        user_key = (body.get('user_key') or 'anonymous').strip()
        exam = _normalize_exam_type(body.get('exam_type', ''))
        try:
            data = practice_service.open_session(
                user_key, exam_type=exam,
                kp_code=body.get('kp_code'),
                qtype=body.get('type'),
                difficulty=body.get('difficulty'),
                count=body.get('count', 5),
                exclude_ids=body.get('exclude_ids'))
            metrics.inc("practice_sessions_total", exam=str(exam or "all"))
            return jsonify({"code": 0, "data": data})
        except Exception as e:  # noqa: BLE001
            logger.error("开练习会话失败: %s", e)
            return jsonify({"code": 1,
                            "message": f"开练习会话失败: {e}"}), 400

    @app.route('/api/practice/session/<sid>/submit', methods=['POST'])
    def submit_practice(sid):
        body = request.get_json(silent=True) or {}
        user_key = (body.get('user_key') or 'anonymous').strip()
        answers = body.get('answers') or []
        if not answers:
            return jsonify({"code": 4001,
                            "message": "answers 不能为空"}), 400
        try:
            data = practice_service.submit(sid, user_key, answers,
                                           response_ms=body.get('response_ms'))
            for r in data["results"]:
                metrics.inc("practice_attempts_total",
                            exam="", is_correct=str(r["correct"]).lower())
            return jsonify({"code": 0, "data": data})
        except Exception as e:  # noqa: BLE001
            logger.error("提交判分失败: %s", e)
            return jsonify({"code": 1, "message": f"提交失败: {e}"}), 400

    @app.route('/api/practice/mistakes', methods=['GET'])
    def practice_mistakes():
        user_key = (request.args.get('user_key') or 'anonymous').strip()
        exam = _normalize_exam_type(request.args.get('exam_type', ''))
        only_pending = request.args.get('pending', 'true').lower() != 'false'
        data = practice_service.list_mistakes(user_key, exam_type=exam,
                                              only_pending=only_pending)
        return jsonify({"code": 0, "data": data})

    @app.route('/api/practice/mistakes/<int:qid>/review', methods=['POST'])
    def review_mistake(qid):
        body = request.get_json(silent=True) or {}
        user_key = (body.get('user_key') or 'anonymous').strip()
        mastered = bool(body.get('mastered', True))
        practice_service.review_mistake(user_key, qid, mastered=mastered)
        return jsonify({"code": 0, "message": "已标记复习"})

    @app.route('/api/practice/stats', methods=['GET'])
    def practice_stats():
        user_key = (request.args.get('user_key') or 'anonymous').strip()
        return jsonify({"code": 0,
                        "data": practice_service.stats(user_key)})

    # ---- 学习计划 ----
    @app.route('/api/study/plans', methods=['GET'])
    def list_plans():
        user_key = (request.args.get('user_key') or 'anonymous').strip()
        return jsonify({"code": 0, "data": practice_service.list_plans(user_key)})

    @app.route('/api/study/plans', methods=['POST'])
    def create_plan():
        body = request.get_json(silent=True) or {}
        user_key = (body.get('user_key') or 'anonymous').strip()
        if not body.get('exam_type'):
            return jsonify({"code": 4001,
                            "message": "exam_type 必填"}), 400
        exam = _normalize_exam_type(body['exam_type'])
        data = practice_service.create_plan(
            user_key, exam, kp_code=body.get('kp_code'),
            difficulty=body.get('difficulty'),
            daily_target=body.get('daily_target', 5))
        return jsonify({"code": 0, "data": data})

    @app.route('/api/study/plans/<int:plan_id>', methods=['DELETE'])
    def toggle_plan(plan_id):
        user_key = (request.args.get('user_key') or 'anonymous').strip()
        data = practice_service.toggle_plan(user_key, plan_id, enabled=False)
        return jsonify({"code": 0, "data": data})

    # ================= V2 M3：专项卷重建 =================
    @app.route('/api/rebuild/papers', methods=['POST'])
    def rebuild_papers_ep():
        body = request.get_json(silent=True) or {}
        exam = _normalize_exam_type(body.get('exam_type', '')) or None
        exams = [exam] if exam else None
        data = _rb(exams=exams, db=db)
        return jsonify({"code": 0, "message": "专项卷已重建",
                        "data": data["rebuilt"]})

    # ================= V2 M3：卷构建登记读取 =================
    @app.route('/api/papers/runs', methods=['GET'])
    def paper_runs():
        exam = _normalize_exam_type(request.args.get('exam_type', '')) or None
        limit = min(int(request.args.get('limit', 10)), 50)
        return jsonify({"code": 0,
                        "data": db.latest_paper_runs(exam_type=exam,
                                                     limit=limit)})

    return app


def _now_str() -> str:
    from datetime import datetime
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ---- 兼容默认实例（供既有测试与 `python -m` 直接启动）----
_default_db = Database()
_default_fetch = FetchService(db=_default_db)
app = create_app(db=_default_db, fetch_service=_default_fetch)
db = _default_db
fetch_service = _default_fetch


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    host = os.environ.get('HOST', '0.0.0.0')
    logging.basicConfig(level=logging.INFO)
    app.run(host=host, port=port, debug=False)
