"""生命周期编排（V2 蓝本 M7 §4.3 / M6 §4）。

定义 bootstrap() 的启动顺序与优雅停机钩子。
业务进程(main.py / 测试)可选择性接入；不强制改写既有调用，保证向后兼容。
"""
from __future__ import annotations

import signal
import threading
import logging
from typing import Callable, List

from src.paths import ensure_dirs

logger = logging.getLogger(__name__)


class App:
    """一个应用运行上下文：依赖容器 + 生命周期回调。"""

    def __init__(self, name: str = "physics-app"):
        self.name = name
        self._deps: dict = {}
        self._start_hooks: List[Callable] = []
        self._stop_hooks: List[Callable] = []
        self._running = False
        self._lock = threading.Lock()

    # ---- DI 容器：依赖注入（对应 D2：去掉模块级全局态） ----
    def register(self, key: str, value) -> None:
        self._deps[key] = value

    def resolve(self, key: str):
        if key not in self._deps:
            raise KeyError(f"依赖未注册: {key}")
        return self._deps[key]

    # ---- 生命周期 ----
    def on_start(self, hook: Callable) -> None:
        self._start_hooks.append(hook)

    def on_stop(self, hook: Callable) -> None:
        self._stop_hooks.append(hook)

    def start(self) -> None:
        """按注册顺序执行启动钩子。"""
        with self._lock:
            if self._running:
                return
            for hook in self._start_hooks:
                hook()
            self._running = True
        logger.info("应用 [%s] 启动完成", self.name)

    def stop(self) -> None:
        """逆序执行停止钩子（优雅停机：先业务后连接）。"""
        with self._lock:
            if not self._running:
                return
            for hook in reversed(self._stop_hooks):
                try:
                    hook()
                except Exception as e:  # noqa: BLE001
                    logger.warning("停止钩子异常: %s", e)
            self._running = False
        logger.info("应用 [%s] 已优雅停机", self.name)

    def run_with_signal(self) -> None:
        """注册 SIGINT/SIGTERM 优雅停机并阻塞主线程。"""
        def _handler(signum, frame):  # noqa: ANN001
            logger.info("收到信号 %s，开始优雅停机...", signum)
            self.stop()

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)
        try:
            while self._running:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()


def bootstrap() -> App:
    """标准启动顺序：确保目录 → 返回 App 上下文。"""
    ensure_dirs()
    app = App("physics-app")
    return app
