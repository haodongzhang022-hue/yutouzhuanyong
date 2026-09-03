#!/usr/bin/env python3
"""单次手动抓取脚本 - 首次初始化或全量抓取"""
import os
import sys
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models.database import Database
from src.services.fetch_service import FetchService

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')


def main():
    """执行一次全量抓取（初始化题库）"""
    db = Database()
    fetch_service = FetchService(db=db)

    print("=" * 60)
    print("  AP Physics 专项练习 - 题库初始化")
    print("=" * 60)

    # 全量拉取所有数据源
    print("\n[1/2] 全量拉取题库数据...")
    results = fetch_service.force_fetch_all()
    for exam, res in results.items():
        print(f"  {exam}: 获取 {res['total_fetched']} 道，新增 {res['new']} 道")

    # 统计
    print("\n[2/2] 获取统计...")
    stats = db.get_stats()
    print(f"  当前题库: AP Physics 1 = {stats['ap_physics_1']} 道, "
          f"Physics Bowl D1 = {stats['physics_bowl_d1']} 道, 总计 = {stats['total']} 道")
    print("\n✓ 初始化完成!")


if __name__ == '__main__':
    main()
