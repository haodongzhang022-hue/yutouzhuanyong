"""采集器基类"""
import logging
from abc import ABC, abstractmethod
from typing import List, Dict

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """采集器抽象基类"""

    def __init__(self, name: str = "", source_type: str = "", limit: int = 5):
        self.name = name
        self.source_type = source_type
        self.limit = limit

    @abstractmethod
    def fetch(self, exam_type: str, count: int = 5) -> List[Dict]:
        """采集指定考试类型的题目"""
        pass

    def _normalize(self, raw_question: Dict, exam_type: str) -> Dict:
        """标准化题目数据，补齐必要字段"""
        q = dict(raw_question)
        q['exam_type'] = exam_type
        q['source'] = self.name
        if not q.get('question_type'):
            q['question_type'] = 'multiple_choice'
        if not q.get('difficulty'):
            q['difficulty'] = 'medium'
        if not q.get('options'):
            q['options'] = []
        if not q.get('explanation'):
            q['explanation'] = ''
        return q
