"""内置题库采集器 - 从本地 JSON 文件读取题目"""
import json
import os
import logging
import random
from typing import List, Dict
from .base import BaseCollector
from src.paths import PROJECT_ROOT

logger = logging.getLogger(__name__)


class BuiltinCollector(BaseCollector):
    """从项目内置 JSON 题库获取题目"""

    def __init__(self, file_path: str, name: str = "内置题库",
                 source_type: str = "builtin", limit: int = 5):
        super().__init__(name=name, source_type=source_type, limit=limit)
        self.file_path = file_path
        self._cache = None

    def _resolve_path(self) -> str:
        """将相对路径转换为基于项目根的绝对路径"""
        if os.path.isabs(self.file_path):
            return self.file_path
        return os.path.join(PROJECT_ROOT, self.file_path)

    def _load_questions(self) -> List[Dict]:
        """加载本地题库文件"""
        if self._cache is not None:
            return self._cache
        file_path = self._resolve_path()

        if not os.path.exists(file_path):
            logger.warning("内置题库文件不存在: %s", file_path)
            self._cache = []
            return self._cache

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                self._cache = data
            else:
                self._cache = []
                logger.warning("题库文件格式错误，应为列表: %s", file_path)
        except Exception as e:
            logger.error("加载题库文件失败 %s: %s", file_path, e)
            self._cache = []
        return self._cache

    def fetch(self, exam_type: str, count: int = None) -> List[Dict]:
        """从内置题库随机获取 count 道题目"""
        count = count or self.limit
        all_questions = self._load_questions()
        if not all_questions:
            return []

        sample = random.sample(all_questions, min(count, len(all_questions)))
        return [self._normalize(q, exam_type) for q in sample]
