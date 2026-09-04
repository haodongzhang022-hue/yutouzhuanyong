"""每日定时调度服务"""
import os
import logging
import yaml
from datetime import datetime, date
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.models.database import Database
from src.services.fetch_service import FetchService
from src.paths import DEFAULT_CONFIG_PATH

logger = logging.getLogger(__name__)


class DailyScheduler:
    """每日题目抓取定时调度器"""

    def __init__(self, db: Database = None, fetch_service: FetchService = None):
        self.db = db or Database()
        self.fetch_service = fetch_service or FetchService(db=self.db)
        self.scheduler = BackgroundScheduler(timezone='Asia/Shanghai')
        self._load_config()

    def _load_config(self):
        """加载调度配置"""
        self.scheduler_cfg = {}
        if os.path.exists(DEFAULT_CONFIG_PATH):
            with open(DEFAULT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
            self.scheduler_cfg = cfg.get('scheduler', {})
        else:
            self.scheduler_cfg = {'daily_fetch_time': '08:00',
                                   'daily_fetch_count': 5}

    def _daily_task(self):
        """每日抓取任务回调（练习采集 + 真题持续同步）"""
        today = date.today().isoformat()
        logger.info("开始每日定时任务: %s", today)
        # 1) 练习：多源持续采集同类型题
        try:
            results = self.fetch_service.fetch_daily()
            for exam_type, result in results.items():
                logger.info("[%s] 练习抓取 %s 道，新增 %s 道",
                            exam_type, result.get('total_fetched', 0),
                            result.get('new', 0))
        except Exception as e:
            logger.error("每日练习抓取异常: %s", e)
        # 2) 真题：把 data/realexam/ 新增的授权真题幂等同步入库+重建
        try:
            from src.services.realexam_sync import sync_all
            report = sync_all(db=self.db)
            for exam, r in report["synced"].items():
                logger.info("[%s] 真题同步源 %s 条，新增 %s 条",
                            exam, r.get("source_total", 0), r.get("new", 0))
        except Exception as e:
            logger.error("每日真题同步异常: %s", e)

    def start(self):
        """启动调度器"""
        if not self.scheduler_cfg.get('enabled', True):
            logger.info("调度器未启用")
            return False

        daily_time = self.scheduler_cfg.get('daily_fetch_time', '08:00')
        hour, minute = daily_time.split(':')

        self.scheduler.add_job(
            self._daily_task,
            CronTrigger(hour=int(hour), minute=int(minute)),
            id='daily_fetch',
            name='每日题目抓取',
            replace_existing=True
        )
        self.scheduler.start()
        logger.info("调度器已启动，每天 %s 执行抓取", daily_time)
        return True

    def shutdown(self):
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("调度器已关闭")
