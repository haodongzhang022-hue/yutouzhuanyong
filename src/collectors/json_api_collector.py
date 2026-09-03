"""JSON API 采集器 - 从符合规范的在线 API 获取题目

支持任何返回标准 JSON 数组格式题目的在线题库接口。
例如可对接自建的在线题库服务，或第三方开放 API。
"""
import logging
from typing import List, Dict
import requests
from .base import BaseCollector

logger = logging.getLogger(__name__)


class JsonApiCollector(BaseCollector):
    """从返回 JSON 数组/对象的 API 采集题目。

    支持的响应格式:
      - 直接返回数组: [{"question_text": "...", "correct_answer": "A", ...}]
      - 返回包装对象: {"data": [...], "questions": [...]}

    可通过 `data_path` 配置指定如何从响应中提取题目列表。
    """

    def __init__(self, url: str, name: str = "在线题库API",
                 source_type: str = "json_api", limit: int = 5,
                 headers: dict = None, timeout: int = 15,
                 data_path: str = "questions"):
        """
        Args:
            url: API 接口地址
            name: 数据源名称
            source_type: 数据源类型标识
            limit: 单次拉取上限
            headers: 自定义请求头
            timeout: 请求超时（秒）
            data_path: 响应中题目列表的路径。
                       'questions' 表示从响应 JSON 的 questions 字段取数组；
                       'data.questions' 表示从 data 下的 questions 取；
                       为空则直接使用响应 JSON 本身作为题目列表。
        """
        super().__init__(name=name, source_type=source_type, limit=limit)
        self.url = url
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (compatible; PhysicsTraining/1.0)',
            'Accept': 'application/json'
        }
        self.timeout = timeout
        self.data_path = data_path

    def _fetch_json(self) -> dict:
        """发起请求并解析 JSON 响应"""
        resp = requests.get(self.url, headers=self.headers, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _extract_questions(self, data) -> List[Dict]:
        """从响应 JSON 中提取题目列表"""
        if data_path := self.data_path:
            # 支持点分隔路径，如 'data.questions'
            current = data
            for part in data_path.split('.'):
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    logger.warning("响应中找不到字段路径: %s", self.data_path)
                    return []
            if isinstance(current, list):
                return current
            elif isinstance(current, dict) and 'items' in current:
                return current['items']
            else:
                logger.warning("字段路径 [%s] 不是列表", self.data_path)
                return []
        elif isinstance(data, list):
            return data
        elif isinstance(data, dict) and isinstance(data.get('questions'), list):
            return data['questions']
        elif isinstance(data, dict) and isinstance(data.get('data'), list):
            return data['data']
        return []

    def fetch(self, exam_type: str, count: int = None) -> List[Dict]:
        """从 JSON API 获取题目"""
        count = count or self.limit
        try:
            data = self._fetch_json()
            questions = self._extract_questions(data)
            if not questions:
                logger.warning("来源 [%s] 未获取到题目数据", self.name)
                return []
            return [self._normalize(q, exam_type) for q in questions[:count]]
        except requests.RequestException as e:
            logger.error("请求 %s 失败: %s", self.url, e)
            return []
        except ValueError as e:
            logger.error("响应不是有效 JSON: %s", e)
            return []
        except Exception as e:
            logger.error("采集器 [%s] 出错: %s", self.name, e)
            return []
