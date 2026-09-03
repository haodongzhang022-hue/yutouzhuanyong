"""数据库 Schema 迁移框架（V2 蓝本 M1）。

用法：业务进程 / Database 初始化后调用 `run_migrations(conn)`。
迁移步骤放在本包（`src/models/migrations/`）下，用 `@migration(n)` 注册，
把库从 (n-1) 升到 n；只增不改、幂等。
"""
from __future__ import annotations

import importlib
import os
import logging

logger = logging.getLogger(__name__)

# 目标 schema 版本
SCHEMA_VERSION = 3

# version -> 迁移函数
_MIGRATIONS: dict = {}


def migration(version: int):
    """装饰器：注册一个把库升到 version 的迁移步骤。"""
    def deco(fn):
        _MIGRATIONS[version] = fn
        return fn
    return deco


def _load_steps():
    here = os.path.dirname(os.path.abspath(__file__))
    for fn in sorted(os.listdir(here)):
        if fn.startswith("_") or not fn.endswith(".py"):
            continue
        mod = fn[:-3]
        try:
            importlib.import_module(f"src.models.migrations.{mod}")
        except Exception as e:  # noqa: BLE001
            logger.warning("加载迁移步骤 %s 失败: %s", mod, e)


def _get_version(conn) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def run_migrations(conn, target: int = SCHEMA_VERSION) -> int:
    """把 schema 升级到 target（默认最新），返回 user_version。"""
    _load_steps()
    cur = _get_version(conn)
    for v in sorted(_MIGRATIONS):
        if v > target or v <= cur:
            continue
        logger.info("Schema 迁移 %s -> %s", cur, v)
        try:
            _MIGRATIONS[v](conn)
            conn.execute(f"PRAGMA user_version={v}")
            conn.commit()
            cur = v
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            logger.error("迁移到 v%s 失败，已回滚: %s", v, e)
            raise
    logger.info("Schema 就绪，user_version=%s", cur)
    return cur
