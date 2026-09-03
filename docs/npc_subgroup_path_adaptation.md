# NPC 子组织 3 级路径适配方案

> 适配对象：CNB 平台中子组织（Subgroup）下的仓库与 NPC 协作链路
> 适用仓库：`dongdongxiaozu/yutoujing/` 下的全部仓库（含 `chengjiedaima`、`yutouzhuanyong` 等）
> 适配日期：2026-09-04

---

## 1. 问题背景

之前 `@dongdongxiaozu/dongjiagoushi(架构·总师)` 项目运行在**根组织** `dongdongxiaozu` 下，仓库路径为 2 级（`org/repo`），NPC 协作正常。

将项目迁移/复制到**子组织** `dongdongxiaozu/yutoujing` 下后（如 `chengjiedaima`），仓库路径变为 3 级（`org/subgroup/repo`），出现以下问题：

1. **@ 选择器不自动补全**：star 了根组织的 NPC 仓库，但在子组织仓库中输入 `@` 不弹出已 star 的 NPC
2. **NPC 互相 @ 协作失效**：NPC 角色之间的接力召唤（如 `架构·评审` → `架构·测试`）无法解析正确路径

### 根因

子组织的完整仓库路径为 3 级（`dongdongxiaozu/yutoujing/chengjiedaima`），但从根组织复制过来的代码（`local-agent/handle/resolver.py`）中：

| 代码位置 | 问题 |
|---------|------|
| `_AT_FULL_RE` 正则 | 只匹配 `@org/repo(role)` 2 级路径，无法解析 `@org/subgroup/repo(role)` 3 级路径 |
| `_git_remote_org_repo()` | git remote URL 解析同样只支持 2 级路径 |
| `roles/reviewer.py` | 硬编码 `target_repo="dongjiagoushi"` 和 fallback `@dongdongxiaozu/dongjiagoushi(...)` |
| `roles/tester.py` | 硬编码 relay 路径 `@dongdongxiaozu/dongjiagoushi(...)` |

这导致：NPC 在子组织环境下被 @ 触发后，无法正确解析「当前操作仓库」和「目标角色仓库」的多级路径，协作链条崩溃。

---

## 2. 适配方案

### 2.1 resolver.py — 多级路径支持

核心改动：**org/repo 模型升级为 slug/多级路径模型**。

```python
# 原版：只支持 2 级路径
_AT_FULL_RE = re.compile(
    r"@\s*(?P<full>[\w.-]+/[\w.-]+)\s*(?:\(\s*(?P<role>[^()]+?)\s*\))?"
)

# 适配版：支持 2 级与 3 级+路径
_AT_FULL_RE = re.compile(
    r"@\s*(?P<full>[\w./-]+)\s*(?:\(\s*(?P<role>[^()]+?)\s*\))?"
)
```

新增辅助函数：

```python
def split_slug(slug):
    """将 slug 拆分为 (org_path, repo_name)，org_path 可为多级"""
    parts = slug.rsplit("/", 1)
    return parts[0], parts[1]

def join_slug(org, repo):
    """将 org_path 与 repo_name 拼成完整 slug"""
    return f"{org}/{repo}"
```

### 2.2 git remote 探测 — 多级路径

`_git_remote_org_repo()` 需要正确处理：

```
https://cnb.cool/dongdongxiaozu/yutoujing/chengjiedaima.git
git@cnb.cool:dongdongxiaozu/yutoujing/chengjiedaima.git
```

解析策略：提取 host 后的路径，最后一段为 repo，前面所有段为 org（可多级）。

### 2.3 硬编码路径修正

在 `reviewer.py`、`tester.py` 中：

```python
# 原版（硬编码根组织路径）
target_handle = "@dongdongxiaozu/dongjiagoushi(架构·测试)"
self.resolve(target_repo="dongjiagoushi", role="架构·测试")

# 适配版（运行时动态解析）
target_handle = "@dongdongxiaozu/yutoujing/chengjiedaima(架构·测试)"  # fallback
self.resolve(target_repo=None, role="架构·测试")  # 运行时由 resolver 自动解析
```

---

## 3. 补丁脚本用法

提供了自动补丁脚本 `scripts/patch_subgroup_npc.py`。

### 用法 1：指定目标仓库

```bash
python scripts/patch_subgroup_npc.py --target /path/to/chengjiedaima
```

### 用法 2：指定目标仓库 slug（推荐）

```bash
python scripts/patch_subgroup_npc.py \
  --target /path/to/chengjiedaima \
  --repo-slug "dongdongxiaozu/yutoujing/chengjiedaima"
```

补丁自动备份原文件为 `.bak`，支持安全恢复。

---

## 4. 验证方法

补丁后运行 resolver 验证：

```python
import handle.resolver as r

# 在子组织环境中验证 3 级路径解析
r.parse_at("@dongdongxiaozu/yutoujing/chengjiedaima(架构·总师)")
# → {'org': 'dongdongxiaozu/yutoujing', 'repo': 'chengjiedaima', 'role': '架构·总师'}

# 根组织 2 级路径仍兼容
r.parse_at("@dongdongxiaozu/dongjiagoushi(架构·经理)")
# → {'org': 'dongdongxiaozu', 'repo': 'dongjiagoushi', 'role': '架构·经理'}

# 自动探测当前仓库（子组织环境）
os.environ['CNB_GROUP_SLUG'] = 'dongdongxiaozu/yutoujing'
os.environ['CNB_REPO_NAME'] = 'chengjiedaima'
r.detect_current_org_repo()
# → ('dongdongxiaozu/yutoujing', 'chengjiedaima')
```

---

## 5. 适配范围说明

| 仓库 | 是否需要适配 | 说明 |
|------|------------|------|
| `dongdongxiaozu/yutoujing/chengjiedaima` | **是** | 从根组织复制，含 resolver/roles 硬编码路径 |
| `dongdongxiaozu/yutoujing/yutouzhuanyong` | 部分 | 不含 resolver 代码，但需确保可被根组织 NPC 正确 @ |
| `dongdongxiaozu/yutoujing/bendidsh` | 否 | 不涉及 NPC 协作 |

> **注意**：CNB 平台层的 NPC 选择器自动补全（star 后 @ 选择器列出 NPC）属于平台功能，
> 本适配仅解决代码层的路径解析问题。如果选择器仍不工作，可能需要平台层面修复。
