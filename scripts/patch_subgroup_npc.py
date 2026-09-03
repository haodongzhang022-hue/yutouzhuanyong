#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
子组织 3 级路径适配补丁
======================
用于将 CNB 平台中「从根组织复制到子组织」的 NPC 仓库（如 chengjiedaima
  → dongdongxiaozu/yutoujing/chengjiedaima）的路径解析逻辑从 2 级
  （org/repo）升级为多级（org/subgroup/.../repo）路径支持。

背景问题：
  - 原 `handle/resolver.py` 中的正则只匹配 `@org/repo(role)` 两级路径
  - 子组织仓库的完整路径为 `org/subgroup/repo`（3 级或更多），导致
    @ 引用解析失败 → NPC 互相 @ 协作链条崩溃
  - git remote / 环境变量探测同样只支持两级路径

用法：
  python scripts/patch_subgroup_npc.py [--target TARGET_DIR] [--repo-slug SLUG]

  TARGET_DIR: 目标 NPC 仓库根目录（包含 local-agent/handle/resolver.py）
              默认为当前目录
  REPO_SLUG:  目标仓库的完整 slug（如 dongdongxiaozu/yutoujing/chengjiedaima）
              用于替换代码中硬编码的 fallback 路径。不指定则跳过 fallback 替换
              （resolver 运行时自动解析）。

补丁范围：
  1. local-agent/handle/resolver.py   — 正则与解析逻辑升级为多级路径
  2. local-agent/roles/*.py           — 硬编码 @dongdongxiaozu/dongjiagoushi 引用
                                         与 target_repo 改为动态解析

安全性：
  - 自动备份原文件为 .bak
  - 补丁失败时提示手动恢复
"""
import argparse
import os
import re
import shutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# 补丁 1: resolver.py — 支持多级路径的完整重写
# ---------------------------------------------------------------------------
RESOLVER_NEW_CODE = r'''# -*- coding: utf-8 -*-
"""
自适应 @ 定位解析器（resolver · 核心 · 子组织适配版）
====================================================
把「@谁、@哪个仓库的谁」从写死的字符串，变成**根据触发仓库自动解析**的机制。

子组织适配版（适配 3 级+路径）：
  原版只支持 2 级路径（`org/repo`），在子组织环境下无法解析 3 级+
  路径（`org/subgroup/repo`）。本版将所有正则/解析逻辑升级为多级路径支持，
  兼容根组织 2 级路径与子组织 3+ 级路径。

关键模型升级：
  - `org` / `group` 概念由「单段」升级为「多段路径」（如 `dongdongxiaozu/yutoujing`）
  - 解析 @ 字符串时，用**从右向左匹配仓库名**的策略区分「仓库名」与「路径前缀」
  - git remote 解析也升级为支持多级路径
"""
import os
import re

# ---------------------------------------------------------------------------
# 约定与默认值（仅作为解析回退基线，非写死目标）
# ---------------------------------------------------------------------------
# 当前操作仓库的默认 org/repo（可被环境变量 / git remote / 触发格式覆盖）
DEFAULT_ORG = "dongdongxiaozu"
DEFAULT_REPO = "dongjiagoushi"

# CNB 平台 CodeBuddy 兜底角色名（触发时若未指明角色，用此兜底）
DEFAULT_CODEBUDDY_ROLE = "CodeBuddy"

# 支持的 @ 触发格式 —— 支持 2 级(org/repo) 与 3 级+(org/subgroup/.../repo)
_AT_FULL_RE = re.compile(
    r"@\s*(?P<full>[\w./-]+)\s*(?:\(\s*(?P<role>[^()]+?)\s*\))?"
)
_AT_SINGLE_RE = re.compile(r"@\s*(?P<name>[\w.-]+)")


def _git_remote_org_repo():
    """从 git remote 探测当前**操作仓库**的 org/repo（多级路径支持）。

    支持 2 级（`org/repo.git`）与 3 级+（`org/sub/.../repo.git`）路径。
    失败返回 (None, None)。
    """
    try:
        import subprocess
        out = subprocess.run(
            ["git", "remote", "-v"], capture_output=True, text=True,
            timeout=5, check=False,
        ).stdout
    except Exception:
        return None, None
    first = None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            first = parts[1]
            break
    if not first:
        return None, None

    # 解析 git remote URL 并提取 org/repo 路径
    url = first.strip()
    # 去掉 scheme
    url = re.sub(r'^[a-zA-Z]+://', '', url)
    # 去掉 user@host 中的 user@
    url = re.sub(r'^[\w.-]+@', '', url)

    # 处理 git@host:org/repo 形式
    if ':' in url:
        url = url.split(':', 1)[1]
    else:
        # https://host/org/sub/repo 形式——第一段是 host，丢弃
        url = url.split('/', 1)[1] if '/' in url else url

    parts_all = url.split('/')
    # 去 .git 后缀
    if parts_all and parts_all[-1].endswith('.git'):
        parts_all[-1] = parts_all[-1][:-4]

    if len(parts_all) < 2:
        return None, None

    org = '/'.join(parts_all[:-1])
    repo = parts_all[-1]
    return org, repo


def _env_org_repo():
    """从环境变量探测当前操作仓库的 org/repo（多级路径支持）。

    识别源（按优先级）：
      1. CNB 平台实际注入变量：
         - `CNB_GROUP_SLUG`（仓库所属父组织路径，可为多级）
         - `CNB_REPO_NAME`（仓库名）
         - `CNB_ROOT_SLUG`（根命名空间兜底）
      2. GIT 通用变量：`GIT_ORG` / `GIT_REPO`
    """
    group = os.environ.get("CNB_GROUP_SLUG") or ""
    repo_name = os.environ.get("CNB_REPO_NAME") or ""
    if group and repo_name:
        return group.strip("/"), repo_name.strip("/")
    root = os.environ.get("CNB_ROOT_SLUG") or ""
    if root and repo_name:
        return root.strip("/"), repo_name.strip("/")
    org = os.environ.get("GIT_ORG")
    repo = os.environ.get("GIT_REPO")
    if org and repo:
        return org, repo
    return None, None


def split_slug(slug):
    """将一个仓库完整 slug 拆分为 (org_path, repo_name)。"""
    if "/" not in slug:
        return None, slug
    parts = slug.rsplit("/", 1)
    return parts[0], parts[1]


def join_slug(org, repo):
    """将 org_path 与 repo_name 拼成一个完整 slug。"""
    if not org:
        return repo
    return f"{org}/{repo}"


def detect_current_org_repo():
    """探测当前**操作仓库**的 org/repo（org 可为多级路径）。"""
    org, repo = _env_org_repo()
    if org and repo:
        return org, repo
    org, repo = _git_remote_org_repo()
    if org and repo:
        return org, repo
    return DEFAULT_ORG, DEFAULT_REPO


def parse_at(at_str):
    """解析一个 @ 触发串 → { org, repo, role }。

    org 可为多级路径（如 `dongdongxiaozu/yutoujing`），repo 为最后一段。
    """
    if not at_str:
        return None
    s = at_str.strip()

    # 完整路径匹配（含角色括号）
    m = _AT_FULL_RE.search(s)
    if m:
        full = m.group("full").strip()
        role = m.group("role")
        if "/" in full:
            org, repo = split_slug(full)
            return {
                "org": org,
                "repo": repo,
                "role": (role or DEFAULT_CODEBUDDY_ROLE).strip(),
            }
        # 单名（如 @CodeBuddy）
        if role:
            return {"org": None, "repo": full,
                    "role": role.strip() or DEFAULT_CODEBUDDY_ROLE}
        # 纯单名 @CodeBuddy → fallthrough
        s = f"@{full}"

    # 单名匹配
    m = _AT_SINGLE_RE.search(s)
    if m:
        name = m.group("name").strip()
        org, repo = detect_current_org_repo()
        if "/" in name:
            o, r = split_slug(name)
            return {"org": o, "repo": r, "role": DEFAULT_CODEBUDDY_ROLE}
        return {"org": org, "repo": name, "role": DEFAULT_CODEBUDDY_ROLE}

    # 无 @ 前缀但含括号的裸路径
    if "/" in s and "(" in s:
        body, role = s.split("(", 1)
        role = role.rstrip(")")
        body = body.strip()
        if "/" in body:
            org, repo = split_slug(body)
            return {"org": org, "repo": repo,
                    "role": role.strip() or DEFAULT_CODEBUDDY_ROLE}
    return None


def format_at(org, repo, role=None):
    """按 org/repo/role 生成标准 @ 格式（org 可为多级）。"""
    role = role or DEFAULT_CODEBUDDY_ROLE
    slug = join_slug(org, repo)
    return f"@{slug}({role})"


def is_cross_repo(target_org=None, target_repo=None, current_org=None,
                  current_repo=None):
    """判定目标仓库与当前**操作仓库**是否**跨仓库**。"""
    if not target_org and not target_repo:
        return False
    c_org, c_repo = current_org, current_repo
    if not c_org or not c_repo:
        c_org, c_repo = detect_current_org_repo()
    if target_org and target_org != c_org:
        return True
    if target_repo and target_repo != c_repo:
        return True
    return False


def resolve(at_str=None, target_org=None, target_repo=None, role=None,
            current_org=None, current_repo=None):
    """核心：把『当前触发上下文』解析为『正确的召唤目标』。"""
    # 1) 触发串识别自身 CodeBuddy 角色承载仓库
    trigger = None
    if at_str:
        trigger = parse_at(at_str)
        if trigger is None:
            trigger = {"org": None, "repo": None,
                       "role": DEFAULT_CODEBUDDY_ROLE}

    # 2) 当前操作仓库
    c_org, c_repo = current_org, current_repo
    if not c_org or not c_repo:
        c_org, c_repo = detect_current_org_repo()

    # 3) 目标三要素（优先级：显式 target > 触发串 trigger > 当前操作仓库）
    t_org = target_org
    t_repo = target_repo
    t_role = role
    src = "default"
    explicit = bool(target_org or target_repo or role)
    trig_org = trigger.get("org") if trigger else None
    trig_repo = trigger.get("repo") if trigger else None
    trig_role = trigger.get("role") if trigger else None
    if t_org is None:
        t_org = trig_org
    if t_repo is None:
        t_repo = trig_repo
    if not t_role:
        t_role = trig_role or DEFAULT_CODEBUDDY_ROLE
    if t_org is None:
        t_org = c_org
    if t_repo is None:
        t_repo = c_repo
    if not t_role:
        t_role = DEFAULT_CODEBUDDY_ROLE
    if explicit:
        src = "target"
    elif trigger and trig_org and trig_repo:
        src = "trigger"
    else:
        src = "probe"

    # 4) 跨库判定
    cross = is_cross_repo(t_org, t_repo, c_org, c_repo)

    # 5) 标准 handle
    handle = format_at(t_org, t_repo, t_role)

    # 6) 权限建议
    cur_slug = join_slug(c_org, c_repo) if c_org else c_repo
    tgt_slug = join_slug(t_org, t_repo) if t_org else t_repo
    if cross:
        note = (
            f"目标仓库 {tgt_slug} 与当前操作仓库 {cur_slug} 不同，"
            f"属于跨仓库协作，必须用目标仓库完整 @ 召唤 `{handle}`；"
            f"否则该角色无目标仓库权限（角色权限通常只覆盖其所属仓库）。"
        )
    else:
        note = (
            f"目标仓库 {tgt_slug} 与当前操作仓库一致，可复用本仓库 @ "
            f"`{handle}`（同仓复用，防冗余）；若需更高权限/其他角色，可按 "
            f"`@org/repo(角色)` 显式指定。"
        )

    return {
        "trigger": {
            "org": trigger["org"] if trigger else None,
            "repo": trigger["repo"] if trigger else None,
            "role": trigger["role"] if trigger else None,
        },
        "current": {"org": c_org, "repo": c_repo},
        "target": {"org": t_org, "repo": t_repo, "role": t_role},
        "handle": handle,
        "cross_repo": cross,
        "source": src,
        "permission_note": note,
    }


# 便捷别名
resolve_handle = resolve


__all__ = [
    "DEFAULT_ORG", "DEFAULT_REPO", "DEFAULT_CODEBUDDY_ROLE",
    "detect_current_org_repo", "parse_at", "format_at",
    "is_cross_repo", "resolve", "resolve_handle",
]
'''


# ---------------------------------------------------------------------------
# 补丁 2: roles/*.py — 硬编码路径替换
# ---------------------------------------------------------------------------
def patch_hardcoded_paths(target_dir, repo_slug=None):
    """在 target_dir 下替换硬编码的路径引用。

    替换模式：
      1. `target_repo="dongjiagoushi"` → `target_repo=None`
         （让 resolver 自动解析）
      2. `target_handle = "@dongdongxiaozu/dongjiagoushi(...)"`
         → 用实际 repo_slug 替换（或设为 None 注释让 resolver 处理）
      3. `relay = "@dongdongxiaozu/dongjiagoushi(...)"`
         → 用实际 repo_slug 替换（或保留由 resolver 动态处理）
    """
    changed = []
    py_files = list(Path(target_dir).rglob("*.py"))
    for pf in py_files:
        src = pf.read_text(encoding="utf-8", errors="replace")
        new_src = src
        modified = False

        # --- 替换 1: target_repo 参数 ---
        new_src = re.sub(
            r'target_repo\s*=\s*["\']dongjiagoushi["\']\s*,?\s*',
            'target_repo=None,  # [子组织适配] 运行时由 resolver 自动解析\n'
            '        ',
            new_src,
        )
        if new_src != src:
            modified = True

        # --- 替换 2: 如果指定了 repo_slug，替换 fallback 和 relay 中的硬编码路径 ---
        if repo_slug:
            new_src = re.sub(
                r'@dongdongxiaozu/dongjiagoushi',
                f'@{repo_slug}',
                new_src,
            )
            if new_src != src:
                modified = True

        # 修正替换产生的格式问题（去除可能多余的缩进空格）
        if modified:
            new_src = _fix_indentation(new_src)

            bak = f"{pf}.bak"
            if not Path(bak).exists():
                shutil.copy2(pf, bak)
            pf.write_text(new_src, encoding="utf-8")
            changed.append(str(pf))

    return changed


def _fix_indentation(src):
    """修复替换产生的缩进/换行问题。

    补丁替换 target_repo="xxx", 为 target_repo=None, 时可能产生
    多余换行或不一致的缩进。此函数做基本的行对齐修复。
    """
    # 处理类似:  self.resolve(target_repo=None,  # comment
    #         role="..."）   → 后续行缩进对齐
    lines = src.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # 如果行尾以 ")" 或逗号结尾的补丁注释结尾，且下一行缩进明显不一致
        if ('[子组织适配]' in line and i + 1 < len(lines)):
            next_line = lines[i + 1]
            # 提取当前行行首空格数
            cur_indent = len(line) - len(line.lstrip())
            # 计算调用参数应该有的缩进
            # 找到调用行（如 self.resolve 或 role 之前的行）
            call_indent = cur_indent + 4  # 参数续行通常缩进 4 格
            if next_line.strip() and not next_line.lstrip().startswith('#'):
                nxt = len(next_line) - len(next_line.lstrip())
                if nxt < cur_indent:
                    # 需要重新缩进
                    lines[i + 1] = ' ' * call_indent + next_line.strip()
        result.append(line)
        i += 1
    return '\n'.join(result)


def patch_resolver(target_dir):
    """替换 resolver.py 为新版多级路径支持版本。"""
    resolver_path = Path(target_dir) / "local-agent" / "handle" / "resolver.py"
    if not resolver_path.exists():
        print(f"[skip] resolver.py 不存在: {resolver_path}")
        return False

    # 备份
    bak = f"{resolver_path}.bak"
    if not Path(bak).exists():
        shutil.copy2(resolver_path, bak)
        print(f"[bak] {resolver_path} → {bak}")

    # 判断是否已打过补丁
    src = resolver_path.read_text(encoding="utf-8", errors="replace")
    if "子组织适配版" in src:
        print("[skip] resolver.py 已是子组织适配版，跳过")
        return True

    resolver_path.write_text(RESOLVER_NEW_CODE, encoding="utf-8")
    print(f"[ok] 已打补丁: {resolver_path}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="子组织 3 级路径 NPC 协作适配补丁"
    )
    parser.add_argument(
        "--target", default=".", type=str,
        help="目标 NPC 仓库根目录（默认当前目录）"
    )
    parser.add_argument(
        "--repo-slug", default=None, type=str,
        help="目标仓库完整 slug（如 dongdongxiaozu/yutoujing/chengjiedaima），"
             "用于替换代码中的硬编码 fallback 路径"
    )
    args = parser.parse_args()

    target = os.path.abspath(args.target)
    print(f"=== 子组织 NPC 路径适配补丁 ===")
    print(f"目标目录: {target}")
    if args.repo_slug:
        print(f"Repo slug: {args.repo_slug}")
    print()

    # 1. 打 resolver.py 补丁
    print("--- 补丁 1: resolver.py 多级路径支持 ---")
    ok = patch_resolver(target)

    # 2. 替换硬编码路径
    print("\n--- 补丁 2: 硬编码路径替换 ---")
    changed = patch_hardcoded_paths(target, args.repo_slug)
    if changed:
        for f in changed:
            print(f"  [ok] 已更新: {f}")
    else:
        print("  [info] 未发现需要更新的硬编码路径文件")

    print("\n=== 补丁完成 ===\n")
    if ok:
        print("验证命令（在目标仓库 local-agent 目录下执行）：")
        print("  python3 -c 'import handle.resolver as r; print(r.parse_at(\"@dongdongxiaozu/yutoujing/chengjiedaima(架构·总师)\"))'")
        print("预期输出：{'org': 'dongdongxiaozu/yutoujing', 'repo': 'chengjiedaima', 'role': '架构·总师'}")
    print()
    print("提示：如果 resolver 解析结果不正确，可用 .bak 文件恢复原版后手动修改。")


if __name__ == "__main__":
    main()
