"""统一结构化日志（V2 蓝本 M6 §1）。

提供 get_logger(name)，输出含 request_id / event 等 key=value 字段，
便于按 request_id 链路追查。不打印敏感信息。
"""
from __future__ import annotations

import logging
import sys
import os
import threading

from src.paths import LOGS_DIR

_request_local = threading.local()


def set_request_id(rid: str) -> None:
    """为当前线程绑定 request_id。"""
    _request_local.rid = rid


def get_request_id() -> str:
    return getattr(_request_local, "rid", "-")


def new_request_id() -> str:
    """生成短 request_id（内网自用，不涉密）。"""
    import uuid
    return uuid.uuid4().hex[:12]


class _CtxFilter(logging.Filter):
    """为日志记录附加 request_id 字段。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def get_logger(name: str = __name__) -> logging.Logger:
    """获取带统一格式与上下文过滤的 logger。"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        os.makedirs(LOGS_DIR, exist_ok=True)
        fmt = ("%(asctime)s %(levelname)s [%(module)s:%(lineno)d] "
               "request_id=%(request_id)s %(message)s")
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(logging.Formatter(fmt))
        file_h = logging.FileHandler(
            os.path.join(LOGS_DIR, "app.log"), encoding="utf-8")
        file_h.setFormatter(logging.Formatter(fmt))
        logger.addHandler(stream)
        logger.addHandler(file_h)
        logger.addFilter(_CtxFilter())
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
