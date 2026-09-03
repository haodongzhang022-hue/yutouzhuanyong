"""极简指标输出（V2 蓝本 M6 §3，无外部依赖）。

提供线程安全计数器/直方图与 Prometheus 文本渲染，供 /api/metrics 读取。
数据源接入时改用真实监控后端即可，接口保持不变。
"""
from __future__ import annotations

import threading
import time
from typing import Dict, Tuple
from collections import defaultdict


class Metrics:
    """线程安全的极简指标收集器。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[Tuple[str, ...], float] = defaultdict(float)
        self._gauges: Dict[Tuple[str, ...], float] = {}
        self._hist: Dict[Tuple[str, ...], list] = defaultdict(list)

    def inc(self, name: str, value: float = 1.0, **labels) -> None:
        key = (name,) + tuple(f"{k}={v}" for k, v in sorted(labels.items()))
        with self._lock:
            self._counters[key] += value

    def set_gauge(self, name: str, value: float, **labels) -> None:
        key = (name,) + tuple(f"{k}={v}" for k, v in sorted(labels.items()))
        with self._lock:
            self._gauges[key] = value

    def observe(self, name: str, value: float, **labels) -> None:
        key = (name,) + tuple(f"{k}={v}" for k, v in sorted(labels.items()))
        with self._lock:
            self._hist[key].append(float(value))

    def render(self) -> str:
        """渲染为 Prometheus 文本格式。"""
        lines: list = []
        with self._lock:
            for (name, *labels), val in self._counters.items():
                lab = "{" + ",".join(labels) + "}" if labels else ""
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{name}{lab} {val:g}")
            for (name, *labels), val in self._gauges.items():
                lab = "{" + ",".join(labels) + "}" if labels else ""
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{name}{lab} {val:g}")
            for (name, *labels), vals in self._hist.items():
                lab = "{" + ",".join(labels) + "}" if labels else ""
                lines.append(f"# TYPE {name} histogram")
                lines.append(f"{name}_count{lab} {len(vals)}")
                lines.append(f"{name}_sum{lab} {sum(vals):g}")
        return "\n".join(lines)


# 全局共享实例
metrics = Metrics()
