"""抓取服务 - 编排多源采集器，将获取到的题目保存到数据库"""
import os
import logging
import yaml
from datetime import date
from typing import List, Dict

from src.models.database import Database
from src.collectors.factory import create_collector
from src.paths import DEFAULT_CONFIG_PATH

logger = logging.getLogger(__name__)

# 全量拉取时的最大请求量
FULL_FETCH_COUNT = 9999


class FetchService:
    """题目抓取编排服务"""

    def __init__(self, db: Database = None, config: dict = None):
        self.db = db or Database()
        self.config = config or self._load_default_config()
        self._collectors = {}

    def _load_default_config(self) -> dict:
        """加载默认配置"""
        if os.path.exists(DEFAULT_CONFIG_PATH):
            with open(DEFAULT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        logger.warning("配置文件不存在: %s，使用空配置", DEFAULT_CONFIG_PATH)
        return {}

    def get_collectors(self, exam_type: str) -> List[object]:
        """获取指定考试类型的采集器列表"""
        if exam_type in self._collectors:
            return self._collectors[exam_type]

        collectors = []
        collectors_cfg = (self.config or {}).get('collectors', {})
        exam_cfg = collectors_cfg.get(exam_type, {})
        if not exam_cfg.get('enabled', True):
            logger.info("考试类型 %s 未启用采集", exam_type)
            return []

        per_source_limit = exam_cfg.get('per_source_limit', 3)
        sources = exam_cfg.get('sources', [])
        for source in sources:
            source = dict(source)
            source['limit'] = source.get('limit', per_source_limit)
            collector = create_collector(source)
            if collector:
                collectors.append(collector)

        self._collectors[exam_type] = collectors
        return collectors

    def fetch_daily(self, exam_types: List[str] = None,
                    daily_count: int = None) -> Dict:
        """执行一次每日抓取任务。"""
        config = self.config or {}
        scheduler_cfg = config.get('scheduler', {})
        exam_type_list = exam_types or ['ap_physics_1', 'physics_bowl_d1']
        daily_limit = daily_count or scheduler_cfg.get('daily_fetch_count', 5)

        today = date.today().isoformat()
        results = {}

        for exam_type in exam_type_list:
            collectors = self.get_collectors(exam_type)
            if not collectors:
                logger.warning("考试类型 %s 没有可用的采集器", exam_type)
                results[exam_type] = {"new": 0, "total_fetched": 0,
                                       "sources": [], "error": "无可用采集器"}
                continue

            exam_result = {"new": 0, "total_fetched": 0, "sources": []}
            total_new = 0
            total_fetched = 0
            for collector in collectors:
                if total_fetched >= daily_limit:
                    break
                batch_size = min(collector.limit, daily_limit - total_fetched)
                try:
                    questions = collector.fetch(exam_type, count=batch_size)
                    total_fetched += len(questions)
                    new_count = self.db.save_questions(questions)
                    total_new += new_count
                    exam_result['sources'].append({
                        "source": collector.name,
                        "fetched": len(questions),
                        "new": new_count
                    })
                    logger.info("来源 [%s] 抓取 %s 道，新增 %s 道",
                                collector.name, len(questions), new_count)
                except Exception as e:
                    logger.error("来源 [%s] 抓取失败: %s", collector.name, e)
                    self.db.log_fetch(exam_type, collector.name, today, 0,
                                      'failed', str(e))

            exam_result['new'] = total_new
            exam_result['total_fetched'] = total_fetched

            status = 'success' if total_fetched > 0 else 'failed'
            self.db.log_fetch(exam_type, 'all_sources', today,
                              total_fetched, status,
                              f"新增{total_new}道")

            results[exam_type] = exam_result

        return results

    def force_fetch_all(self) -> Dict:
        """全量拉取所有数据源（忽略每日限量）"""
        config = self.config or {}
        collectors_cfg = config.get('collectors', {})
        results = {}
        today = date.today().isoformat()

        for exam_type, exam_cfg in collectors_cfg.items():
            if not exam_cfg.get('enabled', True):
                continue
            collectors = self.get_collectors(exam_type)
            if not collectors:
                continue
            total_new = 0
            total_fetched = 0
            for collector in collectors:
                # 全量拉取，请求最大量
                questions = collector.fetch(exam_type, count=FULL_FETCH_COUNT)
                if not questions:
                    continue
                total_fetched += len(questions)
                total_new += self.db.save_questions(questions)
            results[exam_type] = {"new": total_new, "total_fetched": total_fetched}
            self.db.log_fetch(exam_type, 'full_init', today,
                              total_fetched,
                              'success' if total_fetched else 'failed',
                              f"全量初始化，新增{total_new}道")

        return results
