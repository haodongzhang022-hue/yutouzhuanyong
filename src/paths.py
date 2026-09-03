"""项目路径工具"""
import os

# 本文件位于 src/paths.py
# 项目根 = 上级目录 (src/..)
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')
)

CONFIG_DIR = os.path.join(PROJECT_ROOT, 'config')
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
LOGS_DIR = os.path.join(PROJECT_ROOT, 'logs')

DEFAULT_DB_PATH = os.path.join(DATA_DIR, 'physics_bank.db')
DEFAULT_CONFIG_PATH = os.path.join(CONFIG_DIR, 'settings.yaml')
DEFAULT_LOG_PATH = os.path.join(LOGS_DIR, 'app.log')


def ensure_dirs():
    for d in (CONFIG_DIR, DATA_DIR, LOGS_DIR):
        os.makedirs(d, exist_ok=True)
