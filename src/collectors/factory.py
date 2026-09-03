"""采集器工厂"""
import logging
from typing import Dict, List, Optional
from .builtin_collector import BuiltinCollector
from .web_collector import WebCollector
from .json_api_collector import JsonApiCollector

logger = logging.getLogger(__name__)


def create_collector(source_config: dict) -> Optional[object]:
    """根据配置创建采集器实例"""
    source_type = source_config.get('type', '').lower()
    name = source_config.get('name', '')
    limit = source_config.get('limit', 5)

    if source_type == 'builtin':
        return BuiltinCollector(
            file_path=source_config.get('path', ''),
            name=name or '内置题库',
            source_type='builtin',
            limit=limit
        )
    elif source_type in ('json_api', 'api'):
        return JsonApiCollector(
            url=source_config.get('url', ''),
            name=name or '在线题库API',
            source_type='json_api',
            limit=limit,
            headers=source_config.get('headers'),
            timeout=source_config.get('timeout', 15),
            data_path=source_config.get('data_path', 'questions')
        )
    elif source_type == 'web':
        # 对于网页源，需要更具体的实现
        module_name = source_config.get('module')
        if module_name:
            try:
                module = __import__(module_name, fromlist=['collector'])
                cls = getattr(module, 'collector')
                return cls(
                    url=source_config.get('url', ''),
                    name=name,
                    limit=limit,
                    **source_config.get('params', {})
                )
            except Exception as e:
                logger.error("加载自定义采集器 [%s] 失败: %s", module_name, e)
        logger.warning("网页类型采集器需配置 module 指定实现类，当前跳过")
        return None
    else:
        logger.warning("不支持的采集器类型: %s", source_type)
        return None
