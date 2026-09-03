"""主程序入口"""
import os
import sys
import logging
import argparse

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.server import app
from src.services.scheduler import DailyScheduler
from src.paths import LOGS_DIR, ensure_dirs

# 确保目录存在
ensure_dirs()
os.makedirs(LOGS_DIR, exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOGS_DIR, 'app.log'), encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def _init_builtin(scheduler: DailyScheduler):
    """首次启动时全量初始化内置题库"""
    logger.info("首次启动，执行全量题库初始化...")
    try:
        results = scheduler.fetch_service.force_fetch_all()
        for exam, res in results.items():
            logger.info("  初始化 [%s]: 获取 %s 道，新增 %s 道",
                        exam, res.get('total_fetched', 0), res.get('new', 0))
    except Exception as e:
        logger.error("题库初始化失败: %s", e)


def run_scheduler_only():
    """仅运行定时调度器模式"""
    print("=" * 60)
    print("  AP Physics 专项练习 - 每日题目抓取调度器")
    print("=" * 60)
    scheduler = DailyScheduler()
    _init_builtin(scheduler)
    scheduler.start()
    try:
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("正在退出...")
        scheduler.shutdown()


def run_api_mode(host: str = '0.0.0.0', port: int = 8080):
    """运行 API 服务模式（含定时调度）"""
    print("=" * 60)
    print("  AP Physics 专项练习 - 在线 API 服务")
    print("=" * 60)

    try:
        scheduler = DailyScheduler()
        _init_builtin(scheduler)
        scheduler.start()
        logger.info("定时调度器已启动")
    except Exception as e:
        logger.warning("调度器启动失败: %s", e)

    logger.info("API 服务启动: http://%s:%s", host, port)
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='AP Physics 专项练习系统')
    parser.add_argument('--mode', choices=['api', 'scheduler'],
                        default='api', help='运行模式')
    parser.add_argument('--host', default='0.0.0.0', help='绑定地址')
    parser.add_argument('--port', type=int, default=8080, help='端口')
    args = parser.parse_args()

    if args.mode == 'scheduler':
        run_scheduler_only()
    else:
        run_api_mode(host=args.host, port=args.port)
