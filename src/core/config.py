"""配置中心：分层加载 + 启动校验（V2 蓝本 M7 §4.1）。

加载顺序：默认值 < config/settings.yaml < 环境变量(YTZ_) < CLI。
对外提供 load_config() 与 validate_config()，非法配置直接抛 ConfigError。
"""
from __future__ import annotations

import os
import logging
from typing import Dict, Any

from src.paths import PROJECT_ROOT, DEFAULT_CONFIG_PATH

logger = logging.getLogger(__name__)

_ENV_PREFIX = "YTZ_"
# 已知考试枚举
KNOWN_EXAMS = ("ap_physics_1", "physics_bowl_d1")


class ConfigError(Exception):
    """配置非法，拒绝启动。"""


def _default_config() -> Dict[str, Any]:
    """程序内默认值，作为最低基线。"""
    return {
        "app": {"name": "AP Physics 专项练习系统", "version": "2.0.0",
                "debug": False, "host": "0.0.0.0", "port": 8080},
        "database": {"path": "data/physics_bank.db"},
        "scheduler": {"enabled": True, "daily_fetch_time": "08:00",
                      "daily_fetch_count": 5},
        "practice": {"enabled": True},
        "metrics": {"enabled": True},
    }


def _load_yaml(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        logger.warning("配置文件不存在，跳过: %s", path)
        return {}
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception as e:  # noqa: BLE001
        raise ConfigError(f"读取配置 {path} 失败: {e}") from e


def _apply_env(conf: Dict[str, Any]) -> Dict[str, Any]:
    """环境变量 YTZ_APP__PORT / YTZ_DATABASE__PATH 覆盖对应节点。"""
    out = dict(conf)
    for key, val in os.environ.items():
        if not key.startswith(_ENV_PREFIX):
            continue
        parts = key[len(_ENV_PREFIX):].lower().split("__")
        if len(parts) < 2:
            continue
        node = out.setdefault(parts[0], {})
        if not isinstance(node, dict):
            continue
        leaf = parts[-1]
        # 简单类型转换
        if val.isdigit():
            node[leaf] = int(val)
        elif val.lower() in ("true", "false"):
            node[leaf] = val.lower() == "true"
        else:
            node[leaf] = val
    return out


def _validate(conf: Dict[str, Any]) -> None:
    """启动级校验：非法直接抛 ConfigError。"""
    app_cfg = conf.get("app", {})
    # 调度时间格式校验
    sch = conf.get("scheduler", {})
    if sch.get("enabled", True):
        t = sch.get("daily_fetch_time", "08:00")
        try:
            hh, mm = t.split(":")
            if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
                raise ValueError
        except Exception as e:  # noqa: BLE001
            raise ConfigError(
                f"scheduler.daily_fetch_time 非法: {t!r}（期望 HH:MM）") from e
    # 采集器校验
    collectors = conf.get("collectors", {})
    for exam, cfg in collectors.items():
        if not cfg.get("enabled", True):
            continue
        if exam not in KNOWN_EXAMS:
            raise ConfigError(f"未知考试枚举: {exam}")
        sources = cfg.get("sources", [])
        if not sources:
            raise ConfigError(f"考试 {exam} 启用了但 sources 为空")
        for src in sources:
            if not src.get("name") or not src.get("type"):
                raise ConfigError(
                    f"考试 {exam} 的某个 source 缺 name/type")
            if src.get("type") == "builtin" and not src.get("path"):
                raise ConfigError(
                    f"考试 {exam} 的 builtin source 缺 path")
    # 版本号
    if app_cfg.get("version") is None:
        logger.info("app.version 未配置，使用默认")


def load_config(path: str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """加载并校验全量配置，返回合并后的配置字典。"""
    cfg = _default_config()
    cfg.update(_load_yaml(path))
    cfg = _apply_env(cfg)
    _validate(cfg)
    return cfg
