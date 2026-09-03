"""在线 API 服务 - 提供题库查询与练习获取接口"""
import os
import logging
from flask import Flask, jsonify, request

from src.models.database import Database
from src.services.fetch_service import FetchService

logger = logging.getLogger(__name__)

# 支持考试类型的映射
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

app = Flask(__name__)
db = Database()
fetch_service = FetchService(db)


def _normalize_exam_type(value: str) -> str:
    """标准化考试类型"""
    if not value:
        return None
    key = value.strip().lower()
    return EXAM_TYPE_ALIASES.get(key, key)


@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "service": "AP Physics 专项练习系统",
        "time": __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })


@app.route('/api/stats', methods=['GET'])
def stats():
    """获取题库统计信息"""
    data = db.get_stats()
    logs = db.get_fetch_logs(limit=5)
    return jsonify({
        "code": 0,
        "data": {
            "stats": data,
            "recent_logs": logs
        }
    })


@app.route('/api/questions', methods=['GET'])
def get_questions():
    """获取题目列表

    参数:
      exam_type: ap_physics_1 / physics_bowl_d1（可选）
      limit: 数量，默认10
      offset: 偏移，默认0
      topic: 主题筛选（可选）
      difficulty: 难度筛选（可选）
    """
    exam_type = _normalize_exam_type(request.args.get('exam_type', ''))
    limit = min(int(request.args.get('limit', 10)), 100)
    offset = int(request.args.get('offset', 0))
    topic = request.args.get('topic')
    difficulty = request.args.get('difficulty')

    questions = db.get_questions(
        exam_type=exam_type,
        limit=limit,
        offset=offset,
        topic=topic,
        difficulty=difficulty
    )
    total = db.count_questions(exam_type)

    return jsonify({
        "code": 0,
        "data": {
            "total": total,
            "questions": questions
        }
    })


@app.route('/api/questions/<int:qid>', methods=['GET'])
def get_question(qid):
    """获取单道题目详情（含答案与解析）"""
    question = db.get_question_by_id(qid)
    if not question:
        return jsonify({"code": 1, "message": "题目不存在"}), 404
    return jsonify({"code": 0, "data": question})


@app.route('/api/daily/<exam_type>', methods=['GET'])
def get_daily(exam_type):
    """获取每日练习题目（不含答案，用于专项练习）

    参数:
      exam_type: ap_physics_1 / physics_bowl_d1
      count: 题目数量，默认5
      practice_mode: true 时隐藏答案用于做题
    """
    exam = _normalize_exam_type(exam_type)
    if exam not in ('ap_physics_1', 'physics_bowl_d1'):
        return jsonify({"code": 1, "message": "不支持的考试类型"}), 400

    count = min(int(request.args.get('count', 5)), 20)
    practice_mode = request.args.get('practice_mode', 'true').lower() == 'true'

    questions = db.get_daily_questions(exam, count=count)
    if not questions:
        return jsonify({
            "code": 1,
            "message": "题库暂无可用题目，请先执行采集任务",
            "hint": "POST /api/fetch 触发一次采集"
        }), 404

    if practice_mode:
        for q in questions:
            q.pop('correct_answer', None)
            q.pop('explanation', None)

    return jsonify({
        "code": 0,
        "data": {
            "exam_type": exam,
            "count": len(questions),
            "questions": questions
        }
    })


@app.route('/api/fetch', methods=['POST'])
def trigger_fetch():
    """手动触发一次题目采集"""
    body = request.get_json(silent=True) or {}
    exam_types = body.get('exam_types')
    daily_count = body.get('count')

    try:
        results = fetch_service.fetch_daily(
            exam_types=exam_types,
            daily_count=daily_count
        )
        return jsonify({
            "code": 0,
            "message": "采集完成",
            "data": results
        })
    except Exception as e:
        logger.error("手动触发采集失败: %s", e)
        return jsonify({"code": 1, "message": f"采集失败: {str(e)}"}), 500


@app.route('/api/fetch/all', methods=['POST'])
def trigger_fetch_all():
    """强制全量采集（拉取所有可用题目）"""
    try:
        results = fetch_service.force_fetch_all()
        return jsonify({
            "code": 0,
            "message": "全量采集完成",
            "data": results
        })
    except Exception as e:
        logger.error("全量采集失败: %s", e)
        return jsonify({"code": 1, "message": f"采集失败: {str(e)}"}), 500


@app.route('/api/logs', methods=['GET'])
def get_logs():
    """获取最近采集日志"""
    limit = min(int(request.args.get('limit', 20)), 100)
    logs = db.get_fetch_logs(limit=limit)
    return jsonify({"code": 0, "data": logs})


def create_app():
    """工厂函数"""
    return app


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    host = os.environ.get('HOST', '0.0.0.0')
    logging.basicConfig(level=logging.INFO)
    app.run(host=host, port=port, debug=False)
