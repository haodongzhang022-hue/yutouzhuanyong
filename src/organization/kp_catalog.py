"""
知识点目录（Knowledge Point Catalog）

加载 data/catalog/knowledge_points.yaml，
构建 topic(原始英文) -> kp_code 的归并表，
以及 kp_code -> 中文名 对照，供题目规范化使用。
"""
from __future__ import annotations
import os
from typing import Dict, List

import yaml

_DEFAULT_CATALOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "catalog", "knowledge_points.yaml",
)


class KnowledgePointCatalog:
    """统一知识点目录。"""

    def __init__(self, path: str = _DEFAULT_CATALOG):
        self.path = path
        self._alias_to_kp: Dict[str, str] = {}
        self._kp_meta: Dict[str, Dict] = {}
        self._load()

    def _load(self):
        with open(self.path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        for kp in raw.get("knowledge_points", []):
            code = kp["kp_code"]
            self._kp_meta[code] = {
                "kp_name": kp.get("kp_name", ""),
                "kp_name_en": kp.get("kp_name_en", ""),
                "module": kp.get("module", ""),
            }
            # 主名与别名都归一到该码
            self._alias_to_kp[code] = code
            if kp.get("kp_name_en"):
                self._alias_to_kp[kp["kp_name_en"].lower()] = code
            for al in kp.get("aliases", []):
                self._alias_to_kp[al.strip().lower()] = code

    def resolve(self, topic: str) -> str:
        """把原始英文 topic 归一到 kp_code；未命中则原样返回"""
        key = (topic or "").strip().lower()
        return self._alias_to_kp.get(key, topic or "")

    def kp_name(self, kp_code: str) -> str:
        meta = self._kp_meta.get(kp_code, {})
        return meta.get("kp_name", kp_code)

    def kp_name_en(self, kp_code: str) -> str:
        return self._kp_meta.get(kp_code, {}).get("kp_name_en", "")

    def module(self, kp_code: str) -> str:
        return self._kp_meta.get(kp_code, {}).get("module", "")

    def all_kp(self) -> List[Dict]:
        return list(self._kp_meta.values())
