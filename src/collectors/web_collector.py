"""网页采集器 - 从公开网页/API 抓取题目（可扩展模板）"""
import logging
from typing import List, Dict
import requests
from .base import BaseCollector

logger = logging.getLogger(__name__)


class WebCollector(BaseCollector):
    """从网页或 API 采集题目。

    真实在线题库来源可能包含:
      - 开放的公开 REST API
      - 可解析的网页
    此基类提供一个通用的抓取实现模板，
    可通过 URL 配置与解析函数进行适配。
    """

    def __init__(self, url: str, name: str = "网页题库",
                 source_type: str = "web", limit: int = 5,
                 headers: dict = None, timeout: int = 10):
        super().__init__(name=name, source_type=source_type, limit=limit)
        self.url = url
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (compatible; PhysicsTraining/1.0)'
        }
        self.timeout = timeout

    def _request(self) -> requests.Response:
        """发起 HTTP 请求"""
        resp = requests.get(self.url, headers=self.headers, timeout=self.timeout)
        resp.raise_for_status()
        return resp

    def _parse(self, response: requests.Response) -> List[Dict]:
        """子类需覆写此方法以解析响应为题目列表"""
        raise NotImplementedError("WebCollector 的子类需实现 _parse 方法")

    def fetch(self, exam_type: str, count: int = None) -> List[Dict]:
        """抓取并解析题目"""
        count = count or self.limit
        try:
            response = self._request()
            questions = self._parse(response)
            if not questions:
                logger.warning("来源 [%s] 未返回题目数据", self.name)
                return []
            return [self._normalize(q, exam_type) for q in questions[:count]]
        except requests.RequestException as e:
            logger.error("请求 %s 失败: %s", self.url, e)
            return []
        except Exception as e:
            logger.error("采集器 [%s] 出错: %s", self.name, e)
            return []
