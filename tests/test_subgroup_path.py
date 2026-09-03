# -*- coding: utf-8 -*-
"""
子组织 3 级路径适配测试
====================
验证 resolver 在子组织（3 级路径）环境下能正确解析 @ 引用和协作路径。
"""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 从补丁脚本中提取 resolver 代码并加载
PATCH_SCRIPT = Path(__file__).parent.parent / "scripts" / "patch_subgroup_npc.py"


def _load_resolver():
    spec = importlib.util.spec_from_file_location("patch", PATCH_SCRIPT)
    patch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(patch)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(patch.RESOLVER_NEW_CODE)
        tmpfile = f.name

    spec2 = importlib.util.spec_from_file_location("resolver_under_test", tmpfile)
    resolver = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(resolver)
    resolver._tmpfile = tmpfile
    return resolver


class TestResolverSubgroupPath(unittest.TestCase):
    """测试子组织 3 级路径下 resolver 的解析能力"""

    @classmethod
    def setUpClass(cls):
        cls.resolver = _load_resolver()

    @classmethod
    def tearDownClass(cls):
        tmpfile = getattr(cls.resolver, "_tmpfile", None)
        if tmpfile and Path(tmpfile).exists():
            Path(tmpfile).unlink()

    def test_parse_at_3level_path(self):
        """3 级路径（org/subgroup/repo）应正确解析"""
        r = self.resolver.parse_at("@dongdongxiaozu/yutoujing/chengjiedaima(架构·总师)")
        self.assertEqual(r["org"], "dongdongxiaozu/yutoujing")
        self.assertEqual(r["repo"], "chengjiedaima")
        self.assertEqual(r["role"], "架构·总师")

    def test_parse_at_2level_path(self):
        """2 级路径（org/repo）仍然兼容"""
        r = self.resolver.parse_at("@dongdongxiaozu/dongjiagoushi(架构·经理)")
        self.assertEqual(r["org"], "dongdongxiaozu")
        self.assertEqual(r["repo"], "dongjiagoushi")
        self.assertEqual(r["role"], "架构·经理")

    def test_split_slug(self):
        """split_slug 正确拆分多级路径"""
        org, repo = self.resolver.split_slug("dongdongxiaozu/yutoujing/chengjiedaima")
        self.assertEqual(org, "dongdongxiaozu/yutoujing")
        self.assertEqual(repo, "chengjiedaima")

        org2, repo2 = self.resolver.split_slug("dongdongxiaozu/dongjiagoushi")
        self.assertEqual(org2, "dongdongxiaozu")
        self.assertEqual(repo2, "dongjiagoushi")

    def test_join_slug(self):
        """join_slug 正确拼接多级路径"""
        slug = self.resolver.join_slug("dongdongxiaozu/yutoujing", "chengjiedaima")
        self.assertEqual(slug, "dongdongxiaozu/yutoujing/chengjiedaima")

    def test_format_at_subgroup(self):
        """format_at 在子组织环境生成正确的 @ 格式"""
        h = self.resolver.format_at("dongdongxiaozu/yutoujing", "chengjiedaima", "架构·测试")
        self.assertEqual(h, "@dongdongxiaozu/yutoujing/chengjiedaima(架构·测试)")

    def test_detect_subgroup_env(self):
        """CNB_GROUP_SLUG 为多级路径时可正确探测"""
        old_group = os.environ.get("CNB_GROUP_SLUG")
        old_repo = os.environ.get("CNB_REPO_NAME")
        old_root = os.environ.get("CNB_ROOT_SLUG")
        try:
            os.environ["CNB_GROUP_SLUG"] = "dongdongxiaozu/yutoujing"
            os.environ["CNB_REPO_NAME"] = "chengjiedaima"
            os.environ.pop("CNB_ROOT_SLUG", None)
            c_org, c_repo = self.resolver.detect_current_org_repo()
            self.assertEqual(c_org, "dongdongxiaozu/yutoujing")
            self.assertEqual(c_repo, "chengjiedaima")
        finally:
            # 恢复环境变量
            for k, v in [("CNB_GROUP_SLUG", old_group),
                         ("CNB_REPO_NAME", old_repo),
                         ("CNB_ROOT_SLUG", old_root)]:
                if v is not None:
                    os.environ[k] = v
                else:
                    os.environ.pop(k, None)

    def test_resolve_relay_same_repo(self):
        """在子组织仓库内 @ 协作角色时，handle 指向正确 3 级路径"""
        r = self.resolver.resolve(
            at_str="@dongdongxiaozu/yutoujing/chengjiedaima(架构·评审)",
            role="架构·测试",
            current_org="dongdongxiaozu/yutoujing",
            current_repo="chengjiedaima",
        )
        self.assertEqual(r["handle"], "@dongdongxiaozu/yutoujing/chengjiedaima(架构·测试)")
        self.assertFalse(r["cross_repo"])

    def test_resolve_cross_org(self):
        """跨组织解析（子组织 → 根组织）应指向根组织仓库"""
        r = self.resolver.resolve(
            at_str="@dongdongxiaozu/yutoujing/chengjiedaima(架构·评审)",
            target_org="dongdongxiaozu",
            target_repo="dongjiagoushi",
            role="架构·总师",
            current_org="dongdongxiaozu/yutoujing",
            current_repo="chengjiedaima",
        )
        self.assertEqual(r["handle"], "@dongdongxiaozu/dongjiagoushi(架构·总师)")
        self.assertTrue(r["cross_repo"])


if __name__ == "__main__":
    unittest.main()
